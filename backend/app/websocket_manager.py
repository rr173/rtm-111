import asyncio
import json
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import ProbeTarget, Alert, ProbeResult, ProbeGroup, Dependency, ObservationPoint, Change, ChangeTarget, Incident, IncidentTarget, IncidentAlert, IncidentTimeline, IncidentNote, DispatchedAlert
from .probe_engine import probe_engine
from .observer_engine import observer_engine


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop = None
        self._setup_callbacks()

    def _setup_callbacks(self):
        probe_engine.register_status_callback(self._on_status_update)
        probe_engine.register_alert_callback(self._on_alert)
        probe_engine.register_result_callback(self._on_probe_result)
        observer_engine.register_status_callback(self._on_observers_update)

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, websocket: WebSocket):
        if self._loop is None:
            self._loop = asyncio.get_running_loop()
        await websocket.accept()
        self.active_connections.add(websocket)
        await self._send_snapshot(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    def _calculate_group_status(self, targets: list) -> str:
        active_targets = [t for t in targets if not t.paused]
        if not active_targets:
            return "paused"

        has_down = any(t.status == "down" for t in active_targets)
        has_degraded = any(t.status == "degraded" for t in active_targets)

        if has_down:
            return "down"
        elif has_degraded:
            return "degraded"
        else:
            return "healthy"

    async def _send_snapshot(self, websocket: WebSocket):
        from sqlalchemy.orm import joinedload
        db = SessionLocal()
        try:
            targets = db.query(ProbeTarget).options(
                joinedload(ProbeTarget.group),
                joinedload(ProbeTarget.cascade_source)
            ).all()
            groups = db.query(ProbeGroup).all()
            alerts = db.query(Alert).order_by(Alert.timestamp.desc()).limit(100).all()
            dependencies = db.query(Dependency).options(
                joinedload(Dependency.upstream_target),
                joinedload(Dependency.downstream_target)
            ).all()
            observers = db.query(ObservationPoint).all()
            matrix_data = observer_engine.get_matrix_data()

            targets_data = []
            for t in targets:
                recent_results = db.query(ProbeResult).filter(
                    ProbeResult.target_id == t.id
                ).order_by(ProbeResult.timestamp.desc()).limit(120).all()

                results_data = []
                for r in reversed(recent_results):
                    results_data.append({
                        "timestamp": r.timestamp.isoformat(),
                        "success": r.success,
                        "latency_ms": r.latency_ms,
                        "error_message": r.error_message
                    })

                strategy = probe_engine._get_effective_strategy(t)
                current_interval = probe_engine._get_effective_interval(t)
                in_silent = probe_engine._is_in_silent_window(t)
                next_probe_at = datetime.utcnow() + timedelta(seconds=current_interval)

                cascade_source_name = None
                if t.cascade_source_id and t.cascade_source:
                    cascade_source_name = t.cascade_source.name

                targets_data.append({
                    "id": t.id,
                    "group_id": t.group_id,
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
                    "cascade_source_name": cascade_source_name,
                    "consecutive_failures": t.consecutive_failures,
                    "consecutive_successes": t.consecutive_successes,
                    "last_check": t.last_check.isoformat() if t.last_check else None,
                    "created_at": t.created_at.isoformat(),
                    "degrade_threshold": t.degrade_threshold,
                    "down_threshold": t.down_threshold,
                    "success_threshold": t.success_threshold,
                    "adaptive_enabled": strategy["adaptive_enabled"],
                    "slow_interval": strategy["slow_interval"],
                    "fast_interval": strategy["fast_interval"],
                    "silent_start": strategy["silent_start"],
                    "silent_end": strategy["silent_end"],
                    "current_interval": current_interval,
                    "next_probe_at": next_probe_at.isoformat(),
                    "in_silent_window": in_silent,
                    "recent_results": results_data
                })

            groups_data = []
            for g in groups:
                group_targets = [t for t in targets if t.group_id == g.id]
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
                    "status": self._calculate_group_status(group_targets),
                    "target_count": len(group_targets),
                    "paused_count": sum(1 for t in group_targets if t.paused),
                    "healthy_count": sum(1 for t in group_targets if t.status == "healthy" and not t.paused),
                    "degraded_count": sum(1 for t in group_targets if t.status == "degraded" and not t.paused),
                    "down_count": sum(1 for t in group_targets if t.status == "down" and not t.paused),
                    "created_at": g.created_at.isoformat(),
                    "updated_at": g.updated_at.isoformat()
                })

            alerts_data = []
            for a in alerts:
                alerts_data.append({
                    "id": a.id,
                    "target_id": a.target_id,
                    "target_name": a.target.name if a.target else None,
                    "timestamp": a.timestamp.isoformat(),
                    "from_status": a.from_status,
                    "to_status": a.to_status,
                    "acknowledged": a.acknowledged
                })

            deps_data = []
            for d in dependencies:
                deps_data.append({
                    "id": d.id,
                    "upstream_id": d.upstream_id,
                    "upstream_name": d.upstream_target.name if d.upstream_target else "",
                    "downstream_id": d.downstream_id,
                    "downstream_name": d.downstream_target.name if d.downstream_target else "",
                    "description": d.description,
                    "created_at": d.created_at.isoformat() if d.created_at else None
                })

            observers_data = [
                {
                    "id": o.id,
                    "name": o.name,
                    "region": o.region,
                    "status": o.status,
                    "last_heartbeat": o.last_heartbeat.isoformat() if o.last_heartbeat else None,
                    "description": o.description,
                }
                for o in observers
            ]

            snapshot = {
                "type": "snapshot",
                "targets": targets_data,
                "groups": groups_data,
                "alerts": alerts_data,
                "dependencies": deps_data,
                "observers": observers_data,
                "observation_matrix": matrix_data,
            }
            await websocket.send_json(snapshot)
        finally:
            db.close()

    def _on_status_update(self, data: dict):
        self._safe_broadcast(data)

    def _on_alert(self, data: dict):
        self._safe_broadcast(data)

    def _on_probe_result(self, data: dict):
        self._safe_broadcast(data)

    def _on_observers_update(self, data: dict):
        self._safe_broadcast(data)

    def _safe_broadcast(self, message: dict):
        if self._loop is None:
            return

        try:
            if self._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._broadcast(message),
                    self._loop
                )
        except Exception as e:
            print(f"Broadcast error: {e}")

    def broadcast_dependencies(self):
        from sqlalchemy.orm import joinedload
        db = SessionLocal()
        try:
            dependencies = db.query(Dependency).options(
                joinedload(Dependency.upstream_target),
                joinedload(Dependency.downstream_target)
            ).all()
            deps_data = []
            for d in dependencies:
                deps_data.append({
                    "id": d.id,
                    "upstream_id": d.upstream_id,
                    "upstream_name": d.upstream_target.name if d.upstream_target else "",
                    "downstream_id": d.downstream_id,
                    "downstream_name": d.downstream_target.name if d.downstream_target else "",
                    "description": d.description,
                    "created_at": d.created_at.isoformat() if d.created_at else None
                })
            self._safe_broadcast({
                "type": "dependencies_update",
                "dependencies": deps_data
            })
        finally:
            db.close()

    def broadcast_targets(self):
        from sqlalchemy.orm import joinedload
        db = SessionLocal()
        try:
            targets = db.query(ProbeTarget).options(
                joinedload(ProbeTarget.group),
                joinedload(ProbeTarget.cascade_source)
            ).all()
            targets_data = []
            for t in targets:
                strategy = probe_engine._get_effective_strategy(t)
                current_interval = probe_engine._get_effective_interval(t)
                in_silent = probe_engine._is_in_silent_window(t)
                next_probe_at = datetime.utcnow() + timedelta(seconds=current_interval)

                cascade_source_name = None
                if t.cascade_source_id and t.cascade_source:
                    cascade_source_name = t.cascade_source.name

                targets_data.append({
                    "id": t.id,
                    "group_id": t.group_id,
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
                    "cascade_source_name": cascade_source_name,
                    "consecutive_failures": t.consecutive_failures,
                    "consecutive_successes": t.consecutive_successes,
                    "last_check": t.last_check.isoformat() if t.last_check else None,
                    "created_at": t.created_at.isoformat(),
                    "degrade_threshold": t.degrade_threshold,
                    "down_threshold": t.down_threshold,
                    "success_threshold": t.success_threshold,
                    "adaptive_enabled": strategy["adaptive_enabled"],
                    "slow_interval": strategy["slow_interval"],
                    "fast_interval": strategy["fast_interval"],
                    "silent_start": strategy["silent_start"],
                    "silent_end": strategy["silent_end"],
                    "current_interval": current_interval,
                    "next_probe_at": next_probe_at.isoformat(),
                    "in_silent_window": in_silent
                })
            self._safe_broadcast({
                "type": "targets_snapshot",
                "targets": targets_data
            })
        finally:
            db.close()

    def broadcast_changes_update(self):
        from sqlalchemy.orm import joinedload
        db = SessionLocal()
        try:
            changes = db.query(Change).filter(
                Change.status.in_(["pending", "running"])
            ).options(
                joinedload(Change.targets)
            ).order_by(Change.start_time.desc()).all()

            target_changes_map = {}
            for c in changes:
                for ct in c.targets:
                    if ct.target_id not in target_changes_map:
                        target_changes_map[ct.target_id] = []
                    target_changes_map[ct.target_id].append({
                        "change_id": c.id,
                        "change_name": c.name,
                        "change_status": c.status,
                        "start_time": c.start_time.isoformat() if c.start_time else None
                    })

            changes_data = []
            for c in changes:
                targets = []
                for ct in c.targets:
                    target = db.query(ProbeTarget).filter(ProbeTarget.id == ct.target_id).first()
                    targets.append({
                        "id": ct.id,
                        "target_id": ct.target_id,
                        "target_name": target.name if target else "",
                        "created_at": ct.created_at.isoformat() if ct.created_at else None
                    })
                changes_data.append({
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "planned_time": c.planned_time.isoformat() if c.planned_time else None,
                    "status": c.status,
                    "start_time": c.start_time.isoformat() if c.start_time else None,
                    "end_time": c.end_time.isoformat() if c.end_time else None,
                    "notes": c.notes,
                    "created_by": c.created_by,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                    "targets": targets,
                    "target_count": len(targets)
                })

            self._safe_broadcast({
                "type": "changes_update",
                "changes": changes_data,
                "target_changes_map": target_changes_map
            })
        finally:
            db.close()

    def broadcast_incidents_update(self):
        from sqlalchemy.orm import joinedload
        db = SessionLocal()
        try:
            incidents = db.query(Incident).options(
                joinedload(Incident.targets),
                joinedload(Incident.alerts),
                joinedload(Incident.timeline),
                joinedload(Incident.notes),
            ).order_by(Incident.created_at.desc()).all()

            items_data = []
            for incident in incidents:
                targets_data = []
                for it in incident.targets:
                    target = db.query(ProbeTarget).options(joinedload(ProbeTarget.group)).filter(
                        ProbeTarget.id == it.target_id
                    ).first()
                    targets_data.append({
                        "target_id": it.target_id,
                        "target_name": target.name if target else f"Target-{it.target_id}",
                        "target_status": target.status if target else None,
                        "group_name": target.group.name if target and target.group else None,
                        "role": it.role,
                        "first_alert_at": it.first_alert_at.isoformat() if it.first_alert_at else None,
                        "last_alert_at": it.last_alert_at.isoformat() if it.last_alert_at else None,
                        "max_severity": it.max_severity,
                    })

                alerts_data = []
                for ia in incident.alerts:
                    alert = ia.alert
                    alerts_data.append({
                        "alert_id": alert.id,
                        "target_id": alert.target_id,
                        "target_name": alert.target.name if alert.target else None,
                        "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
                        "from_status": alert.from_status,
                        "to_status": alert.to_status,
                    })

                duration = None
                if incident.status in ["recovering", "resolved"] and incident.recovered_at:
                    duration = int((incident.recovered_at - incident.first_anomaly_at).total_seconds())
                elif incident.status == "active":
                    duration = int((datetime.utcnow() - incident.first_anomaly_at).total_seconds())

                items_data.append({
                    "id": incident.id,
                    "title": incident.title,
                    "description": incident.description,
                    "severity": incident.severity,
                    "status": incident.status,
                    "first_anomaly_at": incident.first_anomaly_at.isoformat() if incident.first_anomaly_at else None,
                    "last_anomaly_at": incident.last_anomaly_at.isoformat() if incident.last_anomaly_at else None,
                    "recovered_at": incident.recovered_at.isoformat() if incident.recovered_at else None,
                    "bleed_over_until": incident.bleed_over_until.isoformat() if incident.bleed_over_until else None,
                    "mitigated": incident.mitigated,
                    "mitigated_at": incident.mitigated_at.isoformat() if incident.mitigated_at else None,
                    "owner": incident.owner,
                    "acknowledged": incident.acknowledged,
                    "acknowledged_at": incident.acknowledged_at.isoformat() if incident.acknowledged_at else None,
                    "acknowledged_by": incident.acknowledged_by,
                    "needs_review": incident.needs_review,
                    "review_notes": incident.review_notes,
                    "parent_incident_id": incident.parent_incident_id,
                    "created_at": incident.created_at.isoformat() if incident.created_at else None,
                    "updated_at": incident.updated_at.isoformat() if incident.updated_at else None,
                    "targets": targets_data,
                    "alerts": alerts_data,
                    "target_count": len(targets_data),
                    "alert_count": len(alerts_data),
                    "duration_seconds": duration,
                })

            active_count = sum(1 for i in incidents if i.status in ["active", "recovering"])
            review_count = sum(1 for i in incidents if i.status == "recovering" and i.needs_review)
            resolved_count = sum(1 for i in incidents if i.status == "resolved")

            self._safe_broadcast({
                "type": "incidents_update",
                "items": items_data,
                "active_count": active_count,
                "review_count": review_count,
                "resolved_count": resolved_count,
            })
        finally:
            db.close()

    def broadcast_maintenance_update(self):
        from .maintenance_engine import maintenance_engine
        from .models import ProbeTarget, ProbeGroup
        from sqlalchemy.orm import joinedload
        db = SessionLocal()
        try:
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            start_time = now - timedelta(days=7)
            end_time = now + timedelta(days=30)

            windows = maintenance_engine.get_windows_for_calendar(
                start_time=start_time,
                end_time=end_time
            )

            targets = db.query(ProbeTarget).filter(ProbeTarget.deprecated == False).all()
            targets_data = []
            for t in targets:
                group_color = t.group.color if t.group else "#3b82f6"
                targets_data.append({
                    "id": t.id,
                    "name": t.name,
                    "group_id": t.group_id,
                    "group_name": t.group.name if t.group else None,
                    "status": t.status,
                    "paused": t.paused,
                    "color": group_color
                })

            self._safe_broadcast({
                "type": "maintenance_update",
                "windows": windows,
                "targets": targets_data
            })
        finally:
            db.close()

    def broadcast_duty_update(self):
        db = SessionLocal()
        try:
            dispatched = db.query(DispatchedAlert).order_by(DispatchedAlert.dispatched_at.desc()).limit(100).all()
            items = []
            for da in dispatched:
                alert = da.alert
                target_name = alert.target.name if alert and alert.target else None
                group_name = None
                if da.group_id:
                    grp = db.query(ProbeGroup).filter(ProbeGroup.id == da.group_id).first()
                    if grp:
                        group_name = grp.name
                items.append({
                    "id": da.id,
                    "alert_id": da.alert_id,
                    "schedule_id": da.schedule_id,
                    "group_id": da.group_id,
                    "group_name": group_name,
                    "primary_person": da.primary_person,
                    "backup_person": da.backup_person,
                    "assigned_to": da.assigned_to,
                    "dispatch_status": da.dispatch_status,
                    "dispatched_at": da.dispatched_at.isoformat() if da.dispatched_at else None,
                    "primary_escalated_at": da.primary_escalated_at.isoformat() if da.primary_escalated_at else None,
                    "backup_escalated_at": da.backup_escalated_at.isoformat() if da.backup_escalated_at else None,
                    "acknowledged_at": da.acknowledged_at.isoformat() if da.acknowledged_at else None,
                    "acknowledged_by": da.acknowledged_by,
                    "resolved_at": da.resolved_at.isoformat() if da.resolved_at else None,
                    "resolved_by": da.resolved_by,
                    "resolution_summary": da.resolution_summary,
                    "response_seconds": da.response_seconds,
                    "alert_target_name": target_name,
                    "alert_from_status": alert.from_status if alert else None,
                    "alert_to_status": alert.to_status if alert else None,
                    "alert_timestamp": alert.timestamp.isoformat() if alert and alert.timestamp else None,
                })
            self._safe_broadcast({
                "type": "duty_update",
                "dispatched_alerts": items,
            })
        finally:
            db.close()

    async def _broadcast(self, message: dict):
        dead_connections = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        for conn in dead_connections:
            self.active_connections.discard(conn)


manager = ConnectionManager()


async def get_target_history(target_id: int, hours: int = 24) -> dict:
    db = SessionLocal()
    try:
        target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
        if not target:
            return {"error": "Target not found"}

        since = datetime.utcnow() - timedelta(hours=hours)
        results = db.query(ProbeResult).filter(
            ProbeResult.target_id == target_id,
            ProbeResult.timestamp >= since
        ).order_by(ProbeResult.timestamp.asc()).all()

        latencies = [r.latency_ms for r in results if r.success and r.latency_ms is not None]
        total = len(results)
        successful = sum(1 for r in results if r.success)
        availability = (successful / total * 100) if total > 0 else 100.0

        p50 = p95 = p99 = None
        if latencies:
            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            p50 = sorted_lat[int(n * 0.5)] if n > 0 else None
            p95 = sorted_lat[int(n * 0.95)] if n > 0 else None
            p99 = sorted_lat[int(n * 0.99)] if n > 0 else None

        results_data = []
        for r in results:
            results_data.append({
                "timestamp": r.timestamp.isoformat(),
                "success": r.success,
                "latency_ms": r.latency_ms,
                "error_message": r.error_message
            })

        return {
            "target_id": target_id,
            "availability": availability,
            "total_checks": total,
            "successful_checks": successful,
            "p50": p50,
            "p95": p95,
            "p99": p99,
            "results": results_data
        }
    finally:
        db.close()
