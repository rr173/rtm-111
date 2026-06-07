import asyncio
import time
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional
import httpx
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import ProbeTarget, ProbeResult, Alert


MAX_CONCURRENT_PROBES = 10


class ProbeEngine:
    def __init__(self):
        self.running = False
        self.tasks: Dict[int, asyncio.Task] = {}
        self.semaphore: Optional[asyncio.Semaphore] = None
        self.status_callbacks: List[Callable] = []
        self.alert_callbacks: List[Callable] = []
        self.result_callbacks: List[Callable] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROBES)

    def register_status_callback(self, callback: Callable):
        self.status_callbacks.append(callback)

    def register_alert_callback(self, callback: Callable):
        self.alert_callbacks.append(callback)

    def register_result_callback(self, callback: Callable):
        self.result_callbacks.append(callback)

    async def start(self):
        self.running = True
        self._loop = asyncio.get_running_loop()
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROBES)

        db = SessionLocal()
        try:
            targets = db.query(ProbeTarget).all()
            for target in targets:
                if not target.paused:
                    self._start_target_task_sync(target.id)
        finally:
            db.close()

    async def stop(self):
        self.running = False
        for task in list(self.tasks.values()):
            task.cancel()
        self.tasks.clear()

    def add_target(self, target_id: int):
        db = SessionLocal()
        try:
            target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
            if target and not target.paused and target_id not in self.tasks:
                self._start_target_task_sync(target_id)
        finally:
            db.close()

    def remove_target(self, target_id: int):
        if target_id in self.tasks:
            task = self.tasks[target_id]
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(task.cancel)
            else:
                task.cancel()
            del self.tasks[target_id]

    def toggle_target(self, target_id: int, paused: bool):
        if paused:
            self.remove_target(target_id)
        else:
            self.add_target(target_id)

    def _start_target_task_sync(self, target_id: int):
        if self._loop is None:
            return

        if self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._start_target_task_async(target_id),
                self._loop
            )
        else:
            self._loop.call_soon(
                lambda: asyncio.create_task(self._run_probe_loop(target_id))
            )

    async def _start_task_async(self, target_id: int):
        if target_id not in self.tasks:
            task = asyncio.create_task(self._run_probe_loop(target_id))
            self.tasks[target_id] = task

    async def _start_target_task_async(self, target_id: int):
        if target_id not in self.tasks:
            task = asyncio.create_task(self._run_probe_loop(target_id))
            self.tasks[target_id] = task
            task.add_done_callback(lambda t: self.tasks.pop(target_id, None))

    async def _run_probe_loop(self, target_id: int):
        while self.running:
            db = SessionLocal()
            try:
                target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
                if not target or target.paused:
                    break

                interval = target.interval

                async with self.semaphore:
                    result = await self._execute_probe(target)
                    self._save_result(db, target, result)
                    self._update_state_machine(db, target, result)
                    db.commit()

                    db.refresh(target)
                    self._notify_result(target, result)

            except Exception as e:
                print(f"Probe error for target {target_id}: {e}")
            finally:
                db.close()

            await asyncio.sleep(interval)

    async def _execute_probe(self, target: ProbeTarget) -> dict:
        start_time = time.time()
        success = False
        error_message = None
        latency_ms = None

        try:
            if target.type == "http":
                success, error_message, latency_ms = await self._probe_http(target)
            elif target.type == "tcp":
                success, error_message, latency_ms = await self._probe_tcp(target)
            else:
                error_message = f"Unknown probe type: {target.type}"
        except Exception as e:
            error_message = str(e)
            latency_ms = (time.time() - start_time) * 1000

        if latency_ms is None:
            latency_ms = (time.time() - start_time) * 1000

        return {
            "success": success,
            "latency_ms": latency_ms,
            "error_message": error_message,
            "timestamp": datetime.utcnow()
        }

    async def _probe_http(self, target: ProbeTarget) -> tuple:
        url = target.address
        timeout = target.timeout
        expected_status = target.expected_status or "200"

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                start = time.time()
                response = await client.get(url)
                latency = (time.time() - start) * 1000

                actual_status = str(response.status_code)
                expected_list = [s.strip() for s in expected_status.split(",")]

                if actual_status in expected_list:
                    return True, None, latency
                else:
                    return False, f"Status code mismatch: expected {expected_status}, got {actual_status}", latency

        except httpx.TimeoutException:
            return False, "Connection timeout", timeout * 1000
        except Exception as e:
            return False, str(e), None

    async def _probe_tcp(self, target: ProbeTarget) -> tuple:
        address = target.address
        timeout = target.timeout

        try:
            if ":" in address:
                host, port = address.rsplit(":", 1)
                port = int(port)
            else:
                return False, "Invalid TCP address format (use host:port)", None

            start = time.time()

            def _connect():
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                try:
                    sock.connect((host, port))
                    sock.close()
                    return True, None
                except Exception as e:
                    return False, str(e)
                finally:
                    try:
                        sock.close()
                    except:
                        pass

            success, error = await asyncio.get_event_loop().run_in_executor(None, _connect)
            latency = (time.time() - start) * 1000

            return success, error, latency

        except Exception as e:
            return False, str(e), None

    def _save_result(self, db: Session, target: ProbeTarget, result: dict):
        probe_result = ProbeResult(
            target_id=target.id,
            timestamp=result["timestamp"],
            success=result["success"],
            latency_ms=result["latency_ms"],
            error_message=result["error_message"]
        )
        db.add(probe_result)

        target.last_check = result["timestamp"]

    def _update_state_machine(self, db: Session, target: ProbeTarget, result: dict):
        old_status = target.status

        if result["success"]:
            target.consecutive_failures = 0
            target.consecutive_successes += 1
        else:
            target.consecutive_successes = 0
            target.consecutive_failures += 1

        new_status = self._calculate_status(target, old_status)

        if new_status != old_status:
            target.status = new_status
            if new_status == "healthy":
                target.consecutive_successes = 0
            else:
                target.consecutive_failures = 0
            alert = Alert(
                target_id=target.id,
                from_status=old_status,
                to_status=new_status,
                timestamp=datetime.utcnow()
            )
            db.add(alert)
            db.flush()

            if not target.silenced:
                self._notify_alert(target, alert)

        self._notify_status_change(target)

    def _calculate_status(self, target: ProbeTarget, current_status: str) -> str:
        if target.consecutive_successes >= 3:
            return "healthy"

        if target.consecutive_failures == 0:
            return current_status

        if current_status == "healthy":
            if target.consecutive_failures >= 2:
                return "degraded"
            return current_status
        elif current_status == "degraded":
            if target.consecutive_failures >= 5:
                return "down"
            return current_status
        elif current_status == "down":
            return "down"

        return current_status

    def _notify_status_change(self, target: ProbeTarget):
        data = {
            "type": "status_update",
            "target": {
                "id": target.id,
                "name": target.name,
                "type": target.type,
                "address": target.address,
                "status": target.status,
                "paused": target.paused,
                "silenced": target.silenced,
                "consecutive_failures": target.consecutive_failures,
                "consecutive_successes": target.consecutive_successes,
                "last_check": target.last_check.isoformat() if target.last_check else None
            }
        }
        for callback in self.status_callbacks:
            try:
                callback(data)
            except Exception as e:
                print(f"Status callback error: {e}")

    def _notify_alert(self, target: ProbeTarget, alert: Alert):
        data = {
            "type": "alert",
            "alert": {
                "id": alert.id,
                "target_id": target.id,
                "target_name": target.name,
                "timestamp": alert.timestamp.isoformat(),
                "from_status": alert.from_status,
                "to_status": alert.to_status,
                "acknowledged": alert.acknowledged
            }
        }
        for callback in self.alert_callbacks:
            try:
                callback(data)
            except Exception as e:
                print(f"Alert callback error: {e}")

    def _notify_result(self, target: ProbeTarget, result: dict):
        data = {
            "type": "probe_result",
            "target_id": target.id,
            "result": {
                "timestamp": result["timestamp"].isoformat(),
                "success": result["success"],
                "latency_ms": result["latency_ms"],
                "error_message": result["error_message"]
            }
        }
        for callback in self.result_callbacks:
            try:
                callback(data)
            except Exception as e:
                print(f"Result callback error: {e}")


probe_engine = ProbeEngine()
