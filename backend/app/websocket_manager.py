import asyncio
import json
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import ProbeTarget, Alert, ProbeResult
from .probe_engine import probe_engine


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop = None
        self._setup_callbacks()

    def _setup_callbacks(self):
        probe_engine.register_status_callback(self._on_status_update)
        probe_engine.register_alert_callback(self._on_alert)
        probe_engine.register_result_callback(self._on_probe_result)

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

    async def _send_snapshot(self, websocket: WebSocket):
        db = SessionLocal()
        try:
            targets = db.query(ProbeTarget).all()
            alerts = db.query(Alert).order_by(Alert.timestamp.desc()).limit(100).all()

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

                targets_data.append({
                    "id": t.id,
                    "name": t.name,
                    "type": t.type,
                    "address": t.address,
                    "interval": t.interval,
                    "timeout": t.timeout,
                    "expected_status": t.expected_status,
                    "paused": t.paused,
                    "silenced": t.silenced,
                    "status": t.status,
                    "consecutive_failures": t.consecutive_failures,
                    "consecutive_successes": t.consecutive_successes,
                    "last_check": t.last_check.isoformat() if t.last_check else None,
                    "created_at": t.created_at.isoformat(),
                    "recent_results": results_data
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

            snapshot = {
                "type": "snapshot",
                "targets": targets_data,
                "alerts": alerts_data
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
