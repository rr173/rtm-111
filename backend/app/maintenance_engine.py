import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from .database import SessionLocal
from .models import MaintenanceWindow, MaintenanceWindowEvent, ProbeTarget, ProbeGroup, Alert


class MaintenanceEngine:
    def __init__(self):
        self.running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._task: Optional[asyncio.Task] = None
        self._status_callbacks: List[Callable] = []
        self._alert_callbacks: List[Callable] = []
        self._check_interval = 30

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def register_status_callback(self, callback: Callable):
        self._status_callbacks.append(callback)

    def register_alert_callback(self, callback: Callable):
        self._alert_callbacks.append(callback)

    async def start(self):
        self.running = True
        self._loop = asyncio.get_running_loop()
        self._task = asyncio.create_task(self._run_scheduler())
        print("Maintenance engine started")

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("Maintenance engine stopped")

    async def _run_scheduler(self):
        while self.running:
            try:
                self._check_maintenance_windows()
            except Exception as e:
                print(f"Maintenance scheduler error: {e}")
                import traceback
                traceback.print_exc()
            await asyncio.sleep(self._check_interval)

    def _check_maintenance_windows(self):
        db = SessionLocal()
        try:
            now = datetime.utcnow()

            scheduled_windows = db.query(MaintenanceWindow).filter(
                and_(
                    MaintenanceWindow.status == "scheduled",
                    MaintenanceWindow.is_cancelled == False,
                    MaintenanceWindow.start_time <= now
                )
            ).all()

            for window in scheduled_windows:
                self._start_maintenance(db, window)

            active_windows = db.query(MaintenanceWindow).filter(
                and_(
                    MaintenanceWindow.status == "active",
                    MaintenanceWindow.is_cancelled == False,
                    MaintenanceWindow.end_time <= now
                )
            ).all()

            for window in active_windows:
                self._end_maintenance(db, window)

            timeout_windows = db.query(MaintenanceWindow).filter(
                and_(
                    MaintenanceWindow.status == "active",
                    MaintenanceWindow.is_cancelled == False,
                    MaintenanceWindow.end_time < now,
                    MaintenanceWindow.timeout_alert_sent == False
                )
            ).all()

            for window in timeout_windows:
                self._send_timeout_alert(db, window)

            db.commit()

            if scheduled_windows or active_windows or timeout_windows:
                self._broadcast_update()

        except Exception as e:
            db.rollback()
            print(f"Check maintenance windows error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()

    def _start_maintenance(self, db: Session, window: MaintenanceWindow):
        target = db.query(ProbeTarget).filter(ProbeTarget.id == window.target_id).first()
        if not target:
            return

        window.status = "active"
        window.actual_start_time = datetime.utcnow()

        target.paused = True
        target.silenced = True

        self._add_event(db, window.id, "started", f"维护窗口已开始，目标 {target.name} 已暂停探测并抑制告警")

        from .probe_engine import probe_engine
        probe_engine.toggle_target(target.id, True)

        self._notify_status_change(window, target, "started")

    def _end_maintenance(self, db: Session, window: MaintenanceWindow):
        target = db.query(ProbeTarget).filter(ProbeTarget.id == window.target_id).first()
        if not target:
            return

        window.status = "completed"
        window.actual_end_time = datetime.utcnow()

        target.paused = False
        target.silenced = False

        self._add_event(db, window.id, "completed", f"维护窗口已结束，目标 {target.name} 已恢复探测")

        from .probe_engine import probe_engine
        probe_engine.toggle_target(target.id, False)

        self._notify_status_change(window, target, "completed")

    def _send_timeout_alert(self, db: Session, window: MaintenanceWindow):
        target = db.query(ProbeTarget).filter(ProbeTarget.id == window.target_id).first()
        if not target:
            return

        window.timeout_alert_sent = True

        alert = Alert(
            target_id=window.target_id,
            timestamp=datetime.utcnow(),
            from_status="maintenance",
            to_status="maintenance_timeout",
            acknowledged=False
        )
        db.add(alert)
        db.flush()

        self._add_event(db, window.id, "timeout", f"维护窗口已超时，超过计划结束时间仍未手动确认完成")

        alert_data = {
            "id": alert.id,
            "target_id": alert.target_id,
            "target_name": target.name,
            "timestamp": alert.timestamp.isoformat(),
            "from_status": alert.from_status,
            "to_status": alert.to_status,
            "acknowledged": alert.acknowledged,
            "window_id": window.id,
            "window_title": window.title,
            "owner": window.owner
        }

        for callback in self._alert_callbacks:
            try:
                callback({"type": "maintenance_timeout", "alert": alert_data, "window": self._window_to_dict(window, target)})
            except Exception as e:
                print(f"Maintenance alert callback error: {e}")

    def _add_event(self, db: Session, window_id: int, event_type: str, message: str, extra_data: dict = None):
        event = MaintenanceWindowEvent(
            window_id=window_id,
            event_type=event_type,
            message=message,
            extra_data=extra_data
        )
        db.add(event)

    def _notify_status_change(self, window: MaintenanceWindow, target: ProbeTarget, change_type: str):
        window_dict = self._window_to_dict(window, target)
        for callback in self._status_callbacks:
            try:
                callback({"type": change_type, "window": window_dict})
            except Exception as e:
                print(f"Maintenance status callback error: {e}")

    def _window_to_dict(self, window: MaintenanceWindow, target: ProbeTarget = None) -> dict:
        if target is None:
            db = SessionLocal()
            try:
                target = db.query(ProbeTarget).filter(ProbeTarget.id == window.target_id).first()
            finally:
                db.close()

        return {
            "id": window.id,
            "target_id": window.target_id,
            "target_name": target.name if target else None,
            "group_id": window.group_id,
            "title": window.title,
            "description": window.description,
            "start_time": window.start_time.isoformat(),
            "end_time": window.end_time.isoformat(),
            "reason": window.reason,
            "owner": window.owner,
            "status": window.status,
            "is_cancelled": window.is_cancelled,
            "actual_start_time": window.actual_start_time.isoformat() if window.actual_start_time else None,
            "actual_end_time": window.actual_end_time.isoformat() if window.actual_end_time else None,
            "timeout_alert_sent": window.timeout_alert_sent,
            "created_at": window.created_at.isoformat(),
            "updated_at": window.updated_at.isoformat()
        }

    def _broadcast_update(self):
        for callback in self._status_callbacks:
            try:
                callback({"type": "update"})
            except Exception as e:
                print(f"Maintenance broadcast error: {e}")

    def check_overlap(self, target_id: int, start_time: datetime, end_time: datetime, exclude_window_id: int = None) -> bool:
        db = SessionLocal()
        try:
            query = db.query(MaintenanceWindow).filter(
                and_(
                    MaintenanceWindow.target_id == target_id,
                    MaintenanceWindow.is_cancelled == False,
                    MaintenanceWindow.status.in_(["scheduled", "active"]),
                    or_(
                        and_(
                            MaintenanceWindow.start_time <= start_time,
                            MaintenanceWindow.end_time > start_time
                        ),
                        and_(
                            MaintenanceWindow.start_time < end_time,
                            MaintenanceWindow.end_time >= end_time
                        ),
                        and_(
                            MaintenanceWindow.start_time >= start_time,
                            MaintenanceWindow.end_time <= end_time
                        )
                    )
                )
            )

            if exclude_window_id:
                query = query.filter(MaintenanceWindow.id != exclude_window_id)

            return query.first() is not None
        finally:
            db.close()

    def cancel_window(self, window_id: int, cancelled_reason: str = None) -> bool:
        db = SessionLocal()
        try:
            window = db.query(MaintenanceWindow).filter(MaintenanceWindow.id == window_id).first()
            if not window:
                return False

            if window.status == "completed" or window.is_cancelled:
                return False

            target = db.query(ProbeTarget).filter(ProbeTarget.id == window.target_id).first()

            if window.status == "active":
                if target:
                    target.paused = False
                    target.silenced = False
                    from .probe_engine import probe_engine
                    probe_engine.toggle_target(target.id, False)

            window.is_cancelled = True
            window.cancelled_at = datetime.utcnow()
            window.cancelled_reason = cancelled_reason
            window.status = "cancelled"

            self._add_event(db, window_id, "cancelled", f"维护窗口已取消：{cancelled_reason or '未提供原因'}")

            db.commit()
            self._broadcast_update()
            return True
        except Exception as e:
            db.rollback()
            print(f"Cancel maintenance window error: {e}")
            return False
        finally:
            db.close()

    def extend_window(self, window_id: int, new_end_time: datetime, extension_reason: str) -> bool:
        db = SessionLocal()
        try:
            window = db.query(MaintenanceWindow).filter(MaintenanceWindow.id == window_id).first()
            if not window:
                return False

            if window.status != "active" and window.status != "scheduled":
                return False

            if window.is_cancelled:
                return False

            if new_end_time <= window.end_time:
                return False

            if self.check_overlap(window.target_id, window.start_time, new_end_time, exclude_window_id=window_id):
                return False

            old_end_time = window.end_time
            window.end_time = new_end_time
            window.extension_reason = extension_reason
            window.timeout_alert_sent = False

            self._add_event(db, window_id, "extended",
                           f"维护窗口已延期：从 {old_end_time.isoformat()} 延期至 {new_end_time.isoformat()}，原因：{extension_reason}",
                           {"old_end_time": old_end_time.isoformat(), "new_end_time": new_end_time.isoformat()})

            db.commit()
            self._broadcast_update()
            return True
        except Exception as e:
            db.rollback()
            print(f"Extend maintenance window error: {e}")
            return False
        finally:
            db.close()

    def get_windows_for_calendar(self, start_time: datetime = None, end_time: datetime = None,
                                 target_id: int = None, group_id: int = None) -> List[dict]:
        db = SessionLocal()
        try:
            query = db.query(MaintenanceWindow).options(
                # 我们将手动加载关联
            )

            if start_time and end_time:
                query = query.filter(
                    or_(
                        and_(
                            MaintenanceWindow.start_time >= start_time,
                            MaintenanceWindow.start_time <= end_time
                        ),
                        and_(
                            MaintenanceWindow.end_time >= start_time,
                            MaintenanceWindow.end_time <= end_time
                        ),
                        and_(
                            MaintenanceWindow.start_time <= start_time,
                            MaintenanceWindow.end_time >= end_time
                        )
                    )
                )

            if target_id:
                query = query.filter(MaintenanceWindow.target_id == target_id)

            if group_id:
                query = query.filter(MaintenanceWindow.group_id == group_id)

            windows = query.order_by(MaintenanceWindow.start_time.asc()).all()

            result = []
            for window in windows:
                target = db.query(ProbeTarget).filter(ProbeTarget.id == window.target_id).first()
                group = db.query(ProbeGroup).filter(ProbeGroup.id == window.group_id).first() if window.group_id else None
                result.append({
                    "id": window.id,
                    "target_id": window.target_id,
                    "target_name": target.name if target else None,
                    "group_id": window.group_id,
                    "group_name": group.name if group else None,
                    "title": window.title,
                    "description": window.description,
                    "start_time": window.start_time.isoformat(),
                    "end_time": window.end_time.isoformat(),
                    "reason": window.reason,
                    "owner": window.owner,
                    "status": window.status,
                    "is_cancelled": window.is_cancelled,
                    "cancelled_at": window.cancelled_at.isoformat() if window.cancelled_at else None,
                    "cancelled_reason": window.cancelled_reason,
                    "actual_start_time": window.actual_start_time.isoformat() if window.actual_start_time else None,
                    "actual_end_time": window.actual_end_time.isoformat() if window.actual_end_time else None,
                    "timeout_alert_sent": window.timeout_alert_sent,
                    "extension_reason": window.extension_reason,
                    "created_by": window.created_by,
                    "created_at": window.created_at.isoformat(),
                    "updated_at": window.updated_at.isoformat(),
                })

            return result
        finally:
            db.close()

    def get_active_windows(self) -> List[dict]:
        now = datetime.utcnow()
        return self.get_windows_for_calendar(
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=1)
        )


maintenance_engine = MaintenanceEngine()
