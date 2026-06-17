import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from .database import SessionLocal
from .models import (
    DutySchedule, DutySlot, DutySwap, DispatchedAlert,
    Alert, ProbeGroup, ProbeTarget,
)


ESCALATION_SECONDS = 300


class DutyEngine:
    def __init__(self):
        self._loop = None
        self._task = None
        self._alert_callback = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def register_alert_callback(self, callback):
        self._alert_callback = callback

    async def start(self):
        self._check_escalations()
        self._task = asyncio.create_task(self._escalation_loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _escalation_loop(self):
        while True:
            try:
                await asyncio.sleep(10)
                changed = self._check_escalations()
                if changed and self._alert_callback:
                    self._alert_callback()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Duty escalation error: {e}")

    def _check_escalations(self):
        db = SessionLocal()
        changed = False
        try:
            now = datetime.utcnow()
            dispatched = db.query(DispatchedAlert).filter(
                DispatchedAlert.dispatch_status.in_(["dispatched", "primary_escalated"])
            ).all()

            for da in dispatched:
                if da.dispatch_status == "dispatched":
                    elapsed = (now - da.dispatched_at).total_seconds()
                    if elapsed >= ESCALATION_SECONDS:
                        da.dispatch_status = "primary_escalated"
                        da.primary_escalated_at = now
                        da.assigned_to = da.backup_person
                        db.commit()
                        changed = True
                        print(f"DispatchedAlert {da.id} escalated to backup {da.backup_person}")

                elif da.dispatch_status == "primary_escalated":
                    elapsed = (now - da.primary_escalated_at).total_seconds()
                    if elapsed >= ESCALATION_SECONDS:
                        da.dispatch_status = "unattended"
                        da.backup_escalated_at = now
                        da.assigned_to = None
                        db.commit()
                        changed = True
                        print(f"DispatchedAlert {da.id} marked as unattended")

            return changed
        except Exception as e:
            print(f"Escalation check error: {e}")
            return False
        finally:
            db.close()

    def dispatch_alert(self, alert_id: int, group_id: int = None):
        db = SessionLocal()
        try:
            schedule = self._find_schedule(db, group_id)
            if not schedule:
                return None

            now = datetime.utcnow()
            day_of_week = now.weekday()
            current_hour = now.hour

            slot = self._find_current_slot(db, schedule.id, day_of_week, current_hour)
            if not slot:
                slot = self._find_nearest_slot(db, schedule.id, day_of_week, current_hour)

            if not slot:
                return None

            primary = slot.primary_person
            backup = slot.backup_person

            active_swap = db.query(DutySwap).filter(
                DutySwap.schedule_id == schedule.id,
                DutySwap.swap_date <= now,
                DutySwap.role == "primary"
            ).order_by(DutySwap.swap_date.desc()).first()

            if active_swap:
                swap_dt = active_swap.swap_date
                if (swap_dt.year == now.year and swap_dt.month == now.month and swap_dt.day == now.day
                        and active_swap.start_hour <= current_hour < active_swap.end_hour):
                    if active_swap.original_person == primary:
                        primary = active_swap.new_person
                    elif active_swap.original_person == backup:
                        backup = active_swap.new_person

            existing = db.query(DispatchedAlert).filter(
                DispatchedAlert.alert_id == alert_id
            ).first()
            if existing:
                return existing

            da = DispatchedAlert(
                alert_id=alert_id,
                schedule_id=schedule.id,
                group_id=group_id,
                primary_person=primary,
                backup_person=backup,
                assigned_to=primary,
                dispatch_status="dispatched",
                dispatched_at=now,
            )
            db.add(da)
            db.commit()
            db.refresh(da)
            if self._alert_callback:
                self._alert_callback()
            return da
        finally:
            db.close()

    def _find_schedule(self, db, group_id: int = None):
        if group_id:
            schedule = db.query(DutySchedule).filter(
                DutySchedule.group_id == group_id
            ).first()
            if schedule:
                return schedule

        default = db.query(DutySchedule).filter(
            DutySchedule.is_default == True
        ).first()
        return default

    def _find_current_slot(self, db, schedule_id, day_of_week, current_hour):
        return db.query(DutySlot).filter(
            DutySlot.schedule_id == schedule_id,
            DutySlot.day_of_week == day_of_week,
            DutySlot.start_hour <= current_hour,
            DutySlot.end_hour > current_hour,
        ).first()

    def _find_nearest_slot(self, db, schedule_id, day_of_week, current_hour):
        slot = db.query(DutySlot).filter(
            DutySlot.schedule_id == schedule_id,
            DutySlot.day_of_week == day_of_week,
        ).first()
        return slot

    def get_overview(self, person: str = None):
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            day_of_week = now.weekday()
            current_hour = now.hour

            default_schedule = db.query(DutySchedule).filter(
                DutySchedule.is_default == True
            ).first()

            current_primary = None
            current_backup = None
            schedule_name = None

            if default_schedule:
                schedule_name = default_schedule.name
                slot = self._find_current_slot(db, default_schedule.id, day_of_week, current_hour)
                if slot:
                    current_primary = slot.primary_person
                    current_backup = slot.backup_person

            pending = db.query(DispatchedAlert).filter(
                DispatchedAlert.dispatch_status == "dispatched"
            ).count()
            escalated = db.query(DispatchedAlert).filter(
                DispatchedAlert.dispatch_status == "primary_escalated"
            ).count()
            unattended = db.query(DispatchedAlert).filter(
                DispatchedAlert.dispatch_status == "unattended"
            ).count()

            resolved_alerts = db.query(DispatchedAlert).filter(
                DispatchedAlert.dispatch_status == "resolved",
                DispatchedAlert.response_seconds != None,
            ).all()

            avg_response = None
            if resolved_alerts:
                avg_response = sum(da.response_seconds for da in resolved_alerts) / len(resolved_alerts)

            my_pending = 0
            my_resolved = 0
            if person:
                my_pending = db.query(DispatchedAlert).filter(
                    DispatchedAlert.assigned_to == person,
                    DispatchedAlert.dispatch_status.in_(["dispatched", "primary_escalated"]),
                ).count()
                my_resolved = db.query(DispatchedAlert).filter(
                    DispatchedAlert.resolved_by == person,
                    DispatchedAlert.dispatch_status == "resolved",
                ).count()

            return {
                "current_primary": current_primary,
                "current_backup": current_backup,
                "current_schedule_name": schedule_name,
                "pending_alert_count": pending,
                "escalated_alert_count": escalated,
                "unattended_alert_count": unattended,
                "avg_response_seconds": avg_response,
                "my_pending_count": my_pending,
                "my_resolved_count": my_resolved,
            }
        finally:
            db.close()

    def get_calendar_week(self, schedule_id: int = None, week_offset: int = 0):
        db = SessionLocal()
        try:
            schedule = None
            if schedule_id:
                schedule = db.query(DutySchedule).filter(DutySchedule.id == schedule_id).first()
            if not schedule:
                schedule = db.query(DutySchedule).filter(DutySchedule.is_default == True).first()
            if not schedule:
                return {"week_start": "", "days": []}

            now = datetime.utcnow()
            monday = now - timedelta(days=now.weekday()) + timedelta(weeks=week_offset)
            monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)

            slots = db.query(DutySlot).filter(
                DutySlot.schedule_id == schedule.id
            ).all()

            swaps = db.query(DutySwap).filter(
                DutySwap.schedule_id == schedule.id,
                DutySwap.swap_date >= monday,
                DutySwap.swap_date < monday + timedelta(days=7),
            ).all()

            days = []
            for i in range(7):
                day_date = monday + timedelta(days=i)
                day_slots = [s for s in slots if s.day_of_week == i]

                day_swaps = [sw for sw in swaps
                             if sw.swap_date.year == day_date.year
                             and sw.swap_date.month == day_date.month
                             and sw.swap_date.day == day_date.day]

                calendar_slots = []
                for s in sorted(day_slots, key=lambda x: x.start_hour):
                    primary = s.primary_person
                    backup = s.backup_person
                    is_swapped = False
                    swap_reason = None

                    for sw in day_swaps:
                        if sw.start_hour == s.start_hour and sw.end_hour == s.end_hour:
                            if sw.role == "primary" and sw.original_person == primary:
                                primary = sw.new_person
                                is_swapped = True
                                swap_reason = sw.reason
                            elif sw.role == "backup" and sw.original_person == backup:
                                backup = sw.new_person
                                is_swapped = True
                                swap_reason = sw.reason

                    calendar_slots.append({
                        "day_of_week": s.day_of_week,
                        "start_hour": s.start_hour,
                        "end_hour": s.end_hour,
                        "primary_person": primary,
                        "backup_person": backup,
                        "is_swapped": is_swapped,
                        "swap_reason": swap_reason,
                    })

                if not calendar_slots:
                    calendar_slots.append({
                        "day_of_week": i,
                        "start_hour": 0,
                        "end_hour": 24,
                        "primary_person": "-",
                        "backup_person": "-",
                        "is_swapped": False,
                        "swap_reason": None,
                    })

                days.append({
                    "date": day_date.strftime("%Y-%m-%d"),
                    "day_of_week": i,
                    "slots": calendar_slots,
                })

            return {
                "week_start": monday.strftime("%Y-%m-%d"),
                "days": days,
            }
        finally:
            db.close()

    def get_person_history(self, person: str, limit: int = 50):
        db = SessionLocal()
        try:
            dispatched = db.query(DispatchedAlert).filter(
                (DispatchedAlert.primary_person == person) |
                (DispatchedAlert.backup_person == person) |
                (DispatchedAlert.assigned_to == person) |
                (DispatchedAlert.acknowledged_by == person) |
                (DispatchedAlert.resolved_by == person)
            ).order_by(DispatchedAlert.dispatched_at.desc()).limit(limit).all()

            total_dispatched = len(dispatched)
            total_acknowledged = sum(1 for d in dispatched if d.acknowledged_by == person)
            total_resolved = sum(1 for d in dispatched if d.resolved_by == person)

            response_times = [d.response_seconds for d in dispatched if d.response_seconds is not None and d.acknowledged_by == person]
            avg_response = None
            if response_times:
                avg_response = sum(response_times) / len(response_times)

            alerts_data = []
            for da in dispatched:
                alert = db.query(Alert).filter(Alert.id == da.alert_id).first()
                target_name = alert.target.name if alert and alert.target else None
                group_name = None
                if da.group_id:
                    grp = db.query(ProbeGroup).filter(ProbeGroup.id == da.group_id).first()
                    if grp:
                        group_name = grp.name

                alerts_data.append({
                    "id": da.id,
                    "alert_id": da.alert_id,
                    "schedule_id": da.schedule_id,
                    "group_id": da.group_id,
                    "group_name": group_name,
                    "primary_person": da.primary_person,
                    "backup_person": da.backup_person,
                    "assigned_to": da.assigned_to,
                    "dispatch_status": da.dispatch_status,
                    "dispatched_at": da.dispatched_at,
                    "primary_escalated_at": da.primary_escalated_at,
                    "backup_escalated_at": da.backup_escalated_at,
                    "acknowledged_at": da.acknowledged_at,
                    "acknowledged_by": da.acknowledged_by,
                    "resolved_at": da.resolved_at,
                    "resolved_by": da.resolved_by,
                    "resolution_summary": da.resolution_summary,
                    "response_seconds": da.response_seconds,
                    "alert_target_name": target_name,
                    "alert_from_status": alert.from_status if alert else None,
                    "alert_to_status": alert.to_status if alert else None,
                    "alert_timestamp": alert.timestamp if alert else None,
                })

            return {
                "person": person,
                "total_dispatched": total_dispatched,
                "total_acknowledged": total_acknowledged,
                "total_resolved": total_resolved,
                "avg_response_seconds": avg_response,
                "alerts": alerts_data,
            }
        finally:
            db.close()


duty_engine = DutyEngine()
