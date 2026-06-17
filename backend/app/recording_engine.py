import asyncio
import json
from typing import Dict, List, Optional, Set
from datetime import datetime
from sqlalchemy.orm import Session, joinedload

from .database import SessionLocal
from .models import (
    RecordingSession, RecordingEvent, ProbeTarget, ProbeGroup,
    Alert, Incident, Dependency,
)
from .probe_engine import probe_engine
from .websocket_manager import manager


class RecordingEngine:
    def __init__(self):
        self.active_session: Optional[RecordingSession] = None
        self.active_session_id: Optional[int] = None
        self.start_time: Optional[datetime] = None
        self.event_sequence: int = 0
        self.filter_target_ids: Set[int] = set()
        self.filter_group_ids: Set[int] = set()
        self.recorded_targets: Set[int] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._callbacks_registered = False
        self._update_task: Optional[asyncio.Task] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def _register_callbacks(self):
        if self._callbacks_registered:
            return
        probe_engine.register_status_callback(self._on_status_update)
        probe_engine.register_alert_callback(self._on_alert)
        probe_engine.register_result_callback(self._on_probe_result)
        self._callbacks_registered = True

    def _is_target_allowed(self, target_id: int, db: Session = None) -> bool:
        if not self.filter_target_ids and not self.filter_group_ids:
            return True

        if target_id in self.filter_target_ids:
            return True

        if self.filter_group_ids and db:
            target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
            if target and target.group_id in self.filter_group_ids:
                return True
        elif self.filter_group_ids:
            for gid in self.filter_group_ids:
                if target_id in self._get_group_target_ids(gid):
                    return True

        return False

    def _get_group_target_ids(self, group_id: int) -> Set[int]:
        db = SessionLocal()
        try:
            targets = db.query(ProbeTarget).filter(ProbeTarget.group_id == group_id).all()
            return {t.id for t in targets}
        finally:
            db.close()

    def _should_filter_event(self, event_type: str, data: dict) -> bool:
        if not self.active_session:
            return True

        target_id = None
        if event_type == "status_update":
            target_id = data.get("target", {}).get("id")
        elif event_type == "alert":
            target_id = data.get("alert", {}).get("target_id")
        elif event_type == "probe_result":
            target_id = data.get("target_id")

        if target_id is None:
            return True

        db = SessionLocal()
        try:
            if not self._is_target_allowed(target_id, db):
                return True
            self.recorded_targets.add(target_id)
            return False
        finally:
            db.close()

    def _on_status_update(self, data: dict):
        if self._should_filter_event("status_update", data):
            return
        self._record_event("status_update", data.get("target", {}).get("id"),
                           data.get("target", {}).get("name"), data)

    def _on_alert(self, data: dict):
        if self._should_filter_event("alert", data):
            return
        self._record_event("alert", data.get("alert", {}).get("target_id"),
                           data.get("alert", {}).get("target_name"), data)

    def _on_probe_result(self, data: dict):
        if self._should_filter_event("probe_result", data):
            return
        target_name = None
        if data.get("result") and data.get("target_id"):
            db = SessionLocal()
            try:
                t = db.query(ProbeTarget).filter(ProbeTarget.id == data["target_id"]).first()
                if t:
                    target_name = t.name
            finally:
                db.close()
        self._record_event("probe_result", data.get("target_id"), target_name, data)

    def _record_event(self, event_type: str, target_id: Optional[int],
                      target_name: Optional[str], payload: dict):
        if not self.active_session or self.start_time is None:
            return

        now = datetime.utcnow()
        relative_ms = int((now - self.start_time).total_seconds() * 1000)
        self.event_sequence += 1

        db = SessionLocal()
        try:
            event = RecordingEvent(
                session_id=self.active_session_id,
                event_type=event_type,
                target_id=target_id,
                target_name=target_name,
                relative_time_ms=relative_ms,
                sequence=self.event_sequence,
                payload=json.loads(json.dumps(payload, default=str))
            )
            db.add(event)

            session = db.query(RecordingSession).filter(
                RecordingSession.id == self.active_session_id
            ).first()
            if session:
                session.recorded_count = self.event_sequence
                session.target_count = len(self.recorded_targets)
                session.duration_seconds = int((now - self.start_time).total_seconds())
                session.updated_at = now

            db.commit()
        except Exception as e:
            print(f"Recording event error: {e}")
            db.rollback()
        finally:
            db.close()

    async def _periodic_update(self):
        while self.active_session:
            try:
                self._broadcast_status()
                db = SessionLocal()
                try:
                    session = db.query(RecordingSession).filter(
                        RecordingSession.id == self.active_session_id
                    ).first()
                    if session:
                        now = datetime.utcnow()
                        session.duration_seconds = int((now - self.start_time).total_seconds())
                        session.updated_at = now
                        db.commit()
                finally:
                    db.close()
            except Exception as e:
                print(f"Periodic update error: {e}")
            await asyncio.sleep(1)

    def _broadcast_status(self):
        if not self.active_session:
            return
        status_data = {
            "type": "recording_status",
            "is_recording": True,
            "session_id": self.active_session_id,
            "session_name": self.active_session.name,
            "started_at": self.start_time.isoformat() if self.start_time else None,
            "duration_seconds": int((datetime.utcnow() - self.start_time).total_seconds()) if self.start_time else 0,
            "recorded_count": self.event_sequence,
            "target_count": len(self.recorded_targets),
        }
        manager._safe_broadcast(status_data)

    def start_recording(self, name: str, description: str = None,
                        filter_target_ids: List[int] = None,
                        filter_group_ids: List[int] = None,
                        tags: List[str] = None,
                        created_by: str = None) -> dict:
        if self.active_session:
            return {"error": "已有录制会话正在进行中，请先停止当前会话"}

        self._register_callbacks()

        db = SessionLocal()
        try:
            session = RecordingSession(
                name=name,
                description=description,
                tags=tags or [],
                status="recording",
                started_at=datetime.utcnow(),
                filter_target_ids=filter_target_ids,
                filter_group_ids=filter_group_ids,
                created_by=created_by,
            )
            db.add(session)
            db.commit()
            db.refresh(session)

            self.active_session = session
            self.active_session_id = session.id
            self.start_time = session.started_at
            self.event_sequence = 0
            self.recorded_targets = set()
            self.filter_target_ids = set(filter_target_ids or [])
            self.filter_group_ids = set(filter_group_ids or [])

            if self._loop and self._loop.is_running():
                self._update_task = asyncio.run_coroutine_threadsafe(
                    self._periodic_update(), self._loop
                )

            self._broadcast_status()

            return {
                "id": session.id,
                "name": session.name,
                "status": "recording",
                "started_at": session.started_at.isoformat(),
            }
        except Exception as e:
            print(f"Start recording error: {e}")
            db.rollback()
            return {"error": str(e)}
        finally:
            db.close()

    def stop_recording(self) -> dict:
        if not self.active_session:
            return {"error": "当前没有正在进行的录制会话"}

        if self._update_task:
            try:
                self._update_task.cancel()
            except:
                pass
            self._update_task = None

        ended_at = datetime.utcnow()
        duration = int((ended_at - self.start_time).total_seconds())

        db = SessionLocal()
        try:
            session = db.query(RecordingSession).filter(
                RecordingSession.id == self.active_session_id
            ).first()
            if session:
                session.status = "completed"
                session.ended_at = ended_at
                session.duration_seconds = duration
                session.recorded_count = self.event_sequence
                session.target_count = len(self.recorded_targets)
                db.commit()

            result = {
                "id": session.id if session else self.active_session_id,
                "name": self.active_session.name,
                "status": "completed",
                "recorded_count": self.event_sequence,
                "target_count": len(self.recorded_targets),
                "duration_seconds": duration,
            }

            manager._safe_broadcast({
                "type": "recording_status",
                "is_recording": False,
                "session_id": None,
                "last_session": result,
            })

            self.active_session = None
            self.active_session_id = None
            self.start_time = None
            self.event_sequence = 0
            self.recorded_targets = set()
            self.filter_target_ids = set()
            self.filter_group_ids = set()

            return result
        except Exception as e:
            print(f"Stop recording error: {e}")
            db.rollback()
            return {"error": str(e)}
        finally:
            db.close()

    def get_recording_status(self) -> dict:
        if not self.active_session:
            return {
                "is_recording": False,
                "session_id": None,
            }
        return {
            "is_recording": True,
            "session_id": self.active_session_id,
            "session_name": self.active_session.name,
            "started_at": self.start_time.isoformat() if self.start_time else None,
            "duration_seconds": int((datetime.utcnow() - self.start_time).total_seconds()) if self.start_time else 0,
            "recorded_count": self.event_sequence,
            "target_count": len(self.recorded_targets),
        }

    def list_sessions(self, skip: int = 0, limit: int = 50) -> dict:
        db = SessionLocal()
        try:
            query = db.query(RecordingSession).order_by(
                RecordingSession.created_at.desc()
            )
            total = query.count()
            sessions = query.offset(skip).limit(limit).all()

            result = []
            for s in sessions:
                result.append({
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "tags": s.tags or [],
                    "status": s.status,
                    "started_at": s.started_at.isoformat() if s.started_at else None,
                    "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                    "duration_seconds": s.duration_seconds,
                    "recorded_count": s.recorded_count,
                    "target_count": s.target_count,
                    "filter_target_ids": s.filter_target_ids or [],
                    "filter_group_ids": s.filter_group_ids or [],
                    "created_by": s.created_by,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "has_playback_snapshot": s.pre_playback_snapshot is not None,
                })
            return {"items": result, "total": total}
        finally:
            db.close()

    def get_session_detail(self, session_id: int) -> dict:
        db = SessionLocal()
        try:
            session = db.query(RecordingSession).options(
                joinedload(RecordingSession.events)
            ).filter(RecordingSession.id == session_id).first()

            if not session:
                return {"error": "会话不存在"}

            event_types_count = {}
            target_ids = set()
            for e in session.events:
                event_types_count[e.event_type] = event_types_count.get(e.event_type, 0) + 1
                if e.target_id:
                    target_ids.add(e.target_id)

            return {
                "id": session.id,
                "name": session.name,
                "description": session.description,
                "tags": session.tags or [],
                "status": session.status,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "duration_seconds": session.duration_seconds,
                "recorded_count": session.recorded_count,
                "target_count": session.target_count,
                "filter_target_ids": session.filter_target_ids or [],
                "filter_group_ids": session.filter_group_ids or [],
                "created_by": session.created_by,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "event_types_count": event_types_count,
                "target_ids": sorted(list(target_ids)),
            }
        finally:
            db.close()

    def delete_session(self, session_id: int) -> dict:
        db = SessionLocal()
        try:
            session = db.query(RecordingSession).filter(
                RecordingSession.id == session_id
            ).first()
            if not session:
                return {"error": "会话不存在"}
            if session.id == self.active_session_id:
                return {"error": "正在录制的会话无法删除，请先停止录制"}

            db.delete(session)
            db.commit()
            return {"success": True, "id": session_id}
        except Exception as e:
            db.rollback()
            return {"error": str(e)}
        finally:
            db.close()

    def update_session(self, session_id: int, name: str = None,
                       description: str = None, tags: List[str] = None) -> dict:
        db = SessionLocal()
        try:
            session = db.query(RecordingSession).filter(
                RecordingSession.id == session_id
            ).first()
            if not session:
                return {"error": "会话不存在"}

            if name is not None:
                session.name = name
            if description is not None:
                session.description = description
            if tags is not None:
                session.tags = tags

            db.commit()
            db.refresh(session)

            return {
                "id": session.id,
                "name": session.name,
                "description": session.description,
                "tags": session.tags or [],
            }
        except Exception as e:
            db.rollback()
            return {"error": str(e)}
        finally:
            db.close()


recording_engine = RecordingEngine()
