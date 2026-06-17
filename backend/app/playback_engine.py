import asyncio
import json
import copy
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session, joinedload

from .database import SessionLocal, engine, Base
from .models import (
    RecordingSession, RecordingEvent, PlaybackSnapshot,
    ProbeTarget, ProbeGroup, Alert, Incident, Dependency,
    ProbeResult,
)
from .probe_engine import probe_engine
from .websocket_manager import manager


class PlaybackEngine:
    def __init__(self):
        self.current_session_id: Optional[int] = None
        self.is_playing: bool = False
        self.is_paused: bool = False
        self.speed: float = 1.0
        self.events: List[RecordingEvent] = []
        self.current_event_index: int = 0
        self.playback_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.playback_started_at: Optional[datetime] = None
        self.virtual_time_ms: int = 0
        self.total_duration_ms: int = 0
        self._pause_event: Optional[asyncio.Event] = None
        self._stop_requested: bool = False

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def _get_state_snapshot(self) -> dict:
        db = SessionLocal()
        try:
            targets = db.query(ProbeTarget).options(
                joinedload(ProbeTarget.group),
                joinedload(ProbeTarget.cascade_source)
            ).all()

            targets_data = []
            for t in targets:
                targets_data.append({
                    "id": t.id,
                    "group_id": t.group_id,
                    "rule_id": t.rule_id,
                    "name": t.name,
                    "type": t.type,
                    "address": t.address,
                    "interval": t.interval,
                    "timeout": t.timeout,
                    "expected_status": t.expected_status,
                    "paused": t.paused,
                    "silenced": t.silenced,
                    "status": t.status,
                    "cascade_affected": t.cascade_affected,
                    "cascade_source_id": t.cascade_source_id,
                    "consecutive_failures": t.consecutive_failures,
                    "consecutive_successes": t.consecutive_successes,
                    "last_check": t.last_check.isoformat() if t.last_check else None,
                    "degrade_threshold": t.degrade_threshold,
                    "down_threshold": t.down_threshold,
                    "success_threshold": t.success_threshold,
                    "adaptive_enabled": t.adaptive_enabled,
                    "slow_interval": t.slow_interval,
                    "fast_interval": t.fast_interval,
                    "silent_start": t.silent_start,
                    "silent_end": t.silent_end,
                    "source_id": t.source_id,
                    "deprecated": t.deprecated,
                    "deprecated_at": t.deprecated_at.isoformat() if t.deprecated_at else None,
                    "last_seen_at": t.last_seen_at.isoformat() if t.last_seen_at else None,
                })

            alerts = db.query(Alert).order_by(Alert.timestamp.desc()).limit(200).all()
            alerts_data = []
            for a in alerts:
                alerts_data.append({
                    "id": a.id,
                    "target_id": a.target_id,
                    "target_name": a.target.name if a.target else None,
                    "timestamp": a.timestamp.isoformat(),
                    "from_status": a.from_status,
                    "to_status": a.to_status,
                    "acknowledged": a.acknowledged,
                    "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
                })

            incidents = db.query(Incident).options(
                joinedload(Incident.targets),
                joinedload(Incident.alerts),
            ).all()
            incidents_data = []
            for inc in incidents:
                incidents_data.append({
                    "id": inc.id,
                    "title": inc.title,
                    "description": inc.description,
                    "severity": inc.severity,
                    "status": inc.status,
                    "first_anomaly_at": inc.first_anomaly_at.isoformat(),
                    "last_anomaly_at": inc.last_anomaly_at.isoformat(),
                    "recovered_at": inc.recovered_at.isoformat() if inc.recovered_at else None,
                    "bleed_over_until": inc.bleed_over_until.isoformat() if inc.bleed_over_until else None,
                    "mitigated": inc.mitigated,
                    "mitigated_at": inc.mitigated_at.isoformat() if inc.mitigated_at else None,
                    "owner": inc.owner,
                    "acknowledged": inc.acknowledged,
                    "acknowledged_at": inc.acknowledged_at.isoformat() if inc.acknowledged_at else None,
                    "acknowledged_by": inc.acknowledged_by,
                    "needs_review": inc.needs_review,
                    "review_notes": inc.review_notes,
                    "parent_incident_id": inc.parent_incident_id,
                })

            groups = db.query(ProbeGroup).all()
            groups_data = []
            for g in groups:
                groups_data.append({
                    "id": g.id,
                    "name": g.name,
                    "description": g.description,
                    "color": g.color,
                    "degrade_threshold": g.degrade_threshold,
                    "down_threshold": g.down_threshold,
                    "success_threshold": g.success_threshold,
                    "adaptive_enabled": g.adaptive_enabled,
                    "slow_interval": g.slow_interval,
                    "fast_interval": g.fast_interval,
                    "silent_start": g.silent_start,
                    "silent_end": g.silent_end,
                })

            dependencies = db.query(Dependency).all()
            deps_data = []
            for d in dependencies:
                deps_data.append({
                    "id": d.id,
                    "upstream_id": d.upstream_id,
                    "downstream_id": d.downstream_id,
                    "description": d.description,
                })

            return {
                "targets": targets_data,
                "alerts": alerts_data,
                "incidents": incidents_data,
                "groups": groups_data,
                "dependencies": deps_data,
                "snapshot_time": datetime.utcnow().isoformat(),
            }
        finally:
            db.close()

    def _save_snapshot(self, session_id: int, snapshot_data: dict):
        db = SessionLocal()
        try:
            existing = db.query(PlaybackSnapshot).filter(
                PlaybackSnapshot.session_id == session_id
            ).first()
            if existing:
                db.delete(existing)
                db.flush()

            snapshot = PlaybackSnapshot(
                session_id=session_id,
                targets_snapshot=json.loads(json.dumps(snapshot_data["targets"], default=str)),
                alerts_snapshot=json.loads(json.dumps(snapshot_data["alerts"], default=str)),
                incidents_snapshot=json.loads(json.dumps(snapshot_data["incidents"], default=str)),
                groups_snapshot=json.loads(json.dumps(snapshot_data["groups"], default=str)),
                dependencies_snapshot=json.loads(json.dumps(snapshot_data["dependencies"], default=str)),
            )
            db.add(snapshot)
            db.commit()
        except Exception as e:
            print(f"Save snapshot error: {e}")
            db.rollback()
        finally:
            db.close()

    def _restore_snapshot(self, session_id: int) -> dict:
        db = SessionLocal()
        try:
            snapshot = db.query(PlaybackSnapshot).filter(
                PlaybackSnapshot.session_id == session_id
            ).first()
            if not snapshot:
                return {"error": "没有找到回放前快照"}

            db.query(Alert).delete()
            db.query(ProbeResult).delete()

            for t_data in snapshot.targets_snapshot:
                target = db.query(ProbeTarget).filter(ProbeTarget.id == t_data["id"]).first()
                if target:
                    target.status = t_data["status"]
                    target.paused = t_data["paused"]
                    target.silenced = t_data["silenced"]
                    target.cascade_affected = t_data["cascade_affected"]
                    target.cascade_source_id = t_data["cascade_source_id"]
                    target.consecutive_failures = t_data["consecutive_failures"]
                    target.consecutive_successes = t_data["consecutive_successes"]
                    target.last_check = datetime.fromisoformat(t_data["last_check"]) if t_data["last_check"] else None

            for a_data in snapshot.alerts_snapshot:
                try:
                    ts = datetime.fromisoformat(a_data["timestamp"])
                except:
                    ts = datetime.utcnow()
                ack_at = datetime.fromisoformat(a_data["acknowledged_at"]) if a_data.get("acknowledged_at") else None
                alert = Alert(
                    id=a_data["id"],
                    target_id=a_data["target_id"],
                    timestamp=ts,
                    from_status=a_data["from_status"],
                    to_status=a_data["to_status"],
                    acknowledged=a_data["acknowledged"],
                    acknowledged_at=ack_at,
                )
                db.merge(alert)

            for inc_data in snapshot.incidents_snapshot:
                inc = db.query(Incident).filter(Incident.id == inc_data["id"]).first()
                if inc:
                    inc.status = inc_data["status"]
                    inc.severity = inc_data["severity"]
                    inc.acknowledged = inc_data["acknowledged"]
                    inc.mitigated = inc_data["mitigated"]
                    inc.needs_review = inc_data["needs_review"]

            db.commit()
            return {"success": True}
        except Exception as e:
            print(f"Restore snapshot error: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
            return {"error": str(e)}
        finally:
            db.close()

    def _broadcast_playback_status(self):
        status_data = {
            "type": "playback_status",
            "is_playing": self.is_playing,
            "is_paused": self.is_paused,
            "session_id": self.current_session_id,
            "speed": self.speed,
            "current_index": self.current_event_index,
            "total_events": len(self.events),
            "virtual_time_ms": self.virtual_time_ms,
            "total_duration_ms": self.total_duration_ms,
            "progress": (self.current_event_index / len(self.events) * 100) if self.events else 0,
        }
        manager._safe_broadcast(status_data)

    def _dispatch_event(self, event: RecordingEvent):
        payload = event.payload
        if not payload:
            return

        if event.event_type == "status_update":
            manager._safe_broadcast(payload)
        elif event.event_type == "alert":
            db = SessionLocal()
            try:
                alert_data = payload.get("alert", {})
                target_id = alert_data.get("target_id")
                from_status = alert_data.get("from_status")
                to_status = alert_data.get("to_status")
                if target_id and from_status and to_status:
                    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
                    if target:
                        target.status = to_status
                        alert = Alert(
                            target_id=target_id,
                            from_status=from_status,
                            to_status=to_status,
                            timestamp=datetime.utcnow(),
                            acknowledged=False,
                        )
                        db.add(alert)
                        db.commit()
                        db.refresh(alert)
                        broadcast_alert = {
                            "type": "alert",
                            "alert": {
                                "id": alert.id,
                                "target_id": target_id,
                                "target_name": target.name,
                                "timestamp": alert.timestamp.isoformat(),
                                "from_status": from_status,
                                "to_status": to_status,
                                "acknowledged": False,
                            }
                        }
                        manager._safe_broadcast(broadcast_alert)
                        manager.broadcast_incidents_update()
            except Exception as e:
                print(f"Dispatch alert error: {e}")
                db.rollback()
            finally:
                db.close()
        elif event.event_type == "probe_result":
            db = SessionLocal()
            try:
                target_id = payload.get("target_id")
                result_data = payload.get("result", {})
                if target_id and result_data:
                    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
                    if target:
                        try:
                            ts = datetime.fromisoformat(result_data.get("timestamp", "").replace("Z", "+00:00"))
                        except:
                            ts = datetime.utcnow()

                        success = result_data.get("success", False)
                        latency = result_data.get("latency_ms")
                        error_msg = result_data.get("error_message")

                        probe_result = ProbeResult(
                            target_id=target_id,
                            timestamp=ts,
                            success=success,
                            latency_ms=latency,
                            error_message=error_msg,
                        )
                        db.add(probe_result)

                        if success:
                            target.consecutive_failures = 0
                            target.consecutive_successes += 1
                        else:
                            target.consecutive_successes = 0
                            target.consecutive_failures += 1

                        target.last_check = ts

                        thresholds = probe_engine._get_effective_thresholds(target)
                        new_status = probe_engine._calculate_status(target, target.status)

                        if new_status != target.status:
                            old_status = target.status
                            target.status = new_status
                            alert = Alert(
                                target_id=target_id,
                                from_status=old_status,
                                to_status=new_status,
                                timestamp=datetime.utcnow(),
                                acknowledged=False,
                            )
                            db.add(alert)
                            db.flush()
                            broadcast_alert = {
                                "type": "alert",
                                "alert": {
                                    "id": alert.id,
                                    "target_id": target_id,
                                    "target_name": target.name,
                                    "timestamp": alert.timestamp.isoformat(),
                                    "from_status": old_status,
                                    "to_status": new_status,
                                    "acknowledged": False,
                                }
                            }
                            manager._safe_broadcast(broadcast_alert)
                            manager.broadcast_incidents_update()

                        db.commit()

                        strategy = probe_engine._get_effective_strategy(target)
                        current_interval = probe_engine._get_effective_interval(target)
                        next_probe_at = datetime.utcnow()
                        status_broadcast = {
                            "type": "status_update",
                            "target": {
                                "id": target.id,
                                "group_id": target.group_id,
                                "name": target.name,
                                "type": target.type,
                                "status": target.status,
                                "paused": target.paused,
                                "silenced": target.silenced,
                                "cascade_affected": target.cascade_affected,
                                "consecutive_failures": target.consecutive_failures,
                                "consecutive_successes": target.consecutive_successes,
                                "last_check": target.last_check.isoformat() if target.last_check else None,
                                "current_interval": current_interval,
                                "next_probe_at": next_probe_at.isoformat(),
                                "adaptive_enabled": strategy["adaptive_enabled"],
                            }
                        }
                        manager._safe_broadcast(status_broadcast)

                    result_broadcast = {
                        "type": "probe_result",
                        "target_id": target_id,
                        "result": result_data,
                    }
                    manager._safe_broadcast(result_broadcast)
            except Exception as e:
                print(f"Dispatch probe_result error: {e}")
                import traceback
                traceback.print_exc()
                db.rollback()
            finally:
                db.close()

    async def _playback_loop(self):
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._stop_requested = False

        try:
            while self.current_event_index < len(self.events) and not self._stop_requested:
                await self._pause_event.wait()
                if self._stop_requested:
                    break

                event = self.events[self.current_event_index]

                if self.current_event_index > 0:
                    prev_event = self.events[self.current_event_index - 1]
                    delay_ms = (event.relative_time_ms - prev_event.relative_time_ms) / self.speed
                    if delay_ms > 0:
                        await asyncio.sleep(delay_ms / 1000.0)

                if self._stop_requested:
                    break
                await self._pause_event.wait()
                if self._stop_requested:
                    break

                self.virtual_time_ms = event.relative_time_ms
                self._dispatch_event(event)
                self.current_event_index += 1

                if self.current_event_index % 5 == 0 or self.current_event_index == len(self.events):
                    self._broadcast_playback_status()

            if not self._stop_requested:
                self.is_playing = False
                self._broadcast_playback_status()
                manager._safe_broadcast({
                    "type": "playback_finished",
                    "session_id": self.current_session_id,
                })
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Playback loop error: {e}")
            import traceback
            traceback.print_exc()
            self.is_playing = False
            self._broadcast_playback_status()

    def start_playback(self, session_id: int, speed: float = 1.0) -> dict:
        if self.is_playing:
            return {"error": "已有回放正在进行中，请先停止当前回放"}

        db = SessionLocal()
        try:
            session = db.query(RecordingSession).options(
                joinedload(RecordingSession.events)
            ).filter(
                RecordingSession.id == session_id,
                RecordingSession.status == "completed"
            ).first()

            if not session:
                return {"error": "录制会话不存在或未完成"}

            if not session.events or len(session.events) == 0:
                return {"error": "该会话没有录制任何事件"}

            events = sorted(session.events, key=lambda e: e.sequence)

            snapshot_data = self._get_state_snapshot()
            self._save_snapshot(session_id, snapshot_data)

            self.current_session_id = session_id
            self.is_playing = True
            self.is_paused = False
            self.speed = speed
            self.events = events
            self.current_event_index = 0
            self.playback_started_at = datetime.utcnow()
            self.virtual_time_ms = 0
            self.total_duration_ms = events[-1].relative_time_ms if events else 0

            for t in db.query(ProbeTarget).all():
                if not t.paused:
                    probe_engine.remove_target(t.id)

            db.commit()

            if self._loop and self._loop.is_running():
                self.playback_task = asyncio.run_coroutine_threadsafe(
                    self._playback_loop(), self._loop
                )

            self._broadcast_playback_status()
            manager.broadcast_targets()

            return {
                "session_id": session_id,
                "session_name": session.name,
                "total_events": len(events),
                "total_duration_ms": self.total_duration_ms,
                "speed": speed,
            }
        except Exception as e:
            print(f"Start playback error: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
            return {"error": str(e)}
        finally:
            db.close()

    def pause_playback(self) -> dict:
        if not self.is_playing:
            return {"error": "当前没有正在进行的回放"}

        self.is_paused = True
        if self._pause_event:
            self._pause_event.clear()
        self._broadcast_playback_status()
        return {"success": True, "is_paused": True}

    def resume_playback(self) -> dict:
        if not self.is_playing or not self.is_paused:
            return {"error": "回放未处于暂停状态"}

        self.is_paused = False
        if self._pause_event:
            self._pause_event.set()
        self._broadcast_playback_status()
        return {"success": True, "is_paused": False}

    def stop_playback(self, restore: bool = True) -> dict:
        if not self.is_playing and not self.is_paused:
            return {"error": "当前没有正在进行的回放"}

        self._stop_requested = True
        self.is_playing = False
        self.is_paused = False

        if self._pause_event:
            self._pause_event.set()

        if self.playback_task:
            try:
                self.playback_task.cancel()
            except:
                pass
            self.playback_task = None

        session_id = self.current_session_id

        if restore and session_id:
            self._restore_snapshot(session_id)

        db = SessionLocal()
        try:
            for t in db.query(ProbeTarget).filter(ProbeTarget.paused == False).all():
                probe_engine.add_target(t.id)
            db.commit()
        except Exception as e:
            print(f"Resume probe tasks error: {e}")
        finally:
            db.close()

        manager.broadcast_targets()
        manager.broadcast_incidents_update()
        manager._send_snapshot(list(manager.active_connections)[0]) if manager.active_connections else None

        self.current_session_id = None
        self.events = []
        self.current_event_index = 0
        self.virtual_time_ms = 0
        self.total_duration_ms = 0
        self.speed = 1.0

        self._broadcast_playback_status()

        return {
            "success": True,
            "session_id": session_id,
            "restored": restore,
        }

    def set_speed(self, speed: float) -> dict:
        if not self.is_playing:
            return {"error": "当前没有正在进行的回放"}
        if speed not in [1.0, 2.0, 5.0, 10.0]:
            return {"error": "不支持的倍速，仅支持 1x, 2x, 5x, 10x"}

        self.speed = speed
        self._broadcast_playback_status()
        return {"success": True, "speed": speed}

    def get_playback_status(self) -> dict:
        return {
            "is_playing": self.is_playing,
            "is_paused": self.is_paused,
            "session_id": self.current_session_id,
            "speed": self.speed,
            "current_index": self.current_event_index,
            "total_events": len(self.events),
            "virtual_time_ms": self.virtual_time_ms,
            "total_duration_ms": self.total_duration_ms,
            "progress": (self.current_event_index / len(self.events) * 100) if self.events else 0,
        }

    def seek_to(self, index: int) -> dict:
        if not self.is_playing:
            return {"error": "当前没有正在进行的回放"}
        if index < 0 or index >= len(self.events):
            return {"error": f"索引超出范围: 0 - {len(self.events) - 1}"}

        self.current_event_index = index
        if index > 0:
            self.virtual_time_ms = self.events[index - 1].relative_time_ms
        else:
            self.virtual_time_ms = 0
        self._broadcast_playback_status()
        return {"success": True, "index": index}


playback_engine = PlaybackEngine()
