import asyncio
import time
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional
import httpx
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import ProbeTarget, ProbeResult, Alert, Dependency
from .rule_engine import rule_engine
from collections import deque


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
        self._interval_cache: Dict[int, int] = {}

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
        if target_id not in self.tasks:
            self._start_target_task_sync(target_id)

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
        from sqlalchemy.orm import joinedload
        while self.running:
            db = SessionLocal()
            try:
                target = db.query(ProbeTarget).options(joinedload(ProbeTarget.group)).filter(ProbeTarget.id == target_id).first()
                if not target or target.paused:
                    break

                in_silent = self._is_in_silent_window(target)
                current_interval = self._get_effective_interval(target)
                next_probe_at = datetime.utcnow() + timedelta(seconds=current_interval)

                self._notify_status_change(target, current_interval, next_probe_at, in_silent)

                if in_silent:
                    sleep_duration = self._get_sleep_until_silent_end(target)
                    await asyncio.sleep(sleep_duration)
                    continue

                async with self.semaphore:
                    result = await self._execute_probe(target)
                    self._save_result(db, target, result)
                    self._update_state_machine(db, target, result)
                    db.commit()

                    db.refresh(target)
                    self._notify_result(target, result)

                    new_interval = self._get_effective_interval(target)
                    new_next_probe = datetime.utcnow() + timedelta(seconds=new_interval)
                    self._notify_status_change(target, new_interval, new_next_probe, False)

            except Exception as e:
                print(f"Probe error for target {target_id}: {e}")
            finally:
                db.close()

            current_interval = self._get_cached_interval(target_id)
            await asyncio.sleep(current_interval if current_interval else target.interval)

    async def _execute_probe(self, target: ProbeTarget) -> dict:
        if target.rule_id:
            return await self._execute_rule_probe(target)

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

    async def _execute_rule_probe(self, target: ProbeTarget) -> dict:
        result = await rule_engine.execute_rule(target)
        return result

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

    def _get_downstream_targets(self, db: Session, target_id: int) -> List[ProbeTarget]:
        visited = set()
        result = []
        queue = deque([target_id])

        while queue:
            current_id = queue.popleft()
            if current_id in visited:
                continue
            visited.add(current_id)

            deps = db.query(Dependency).filter(Dependency.upstream_id == current_id).all()
            for dep in deps:
                if dep.downstream_id not in visited:
                    downstream = db.query(ProbeTarget).filter(ProbeTarget.id == dep.downstream_id).first()
                    if downstream:
                        result.append(downstream)
                        queue.append(dep.downstream_id)

        return result

    def _get_upstream_targets(self, db: Session, target_id: int) -> List[ProbeTarget]:
        visited = set()
        result = []
        queue = deque([target_id])

        while queue:
            current_id = queue.popleft()
            if current_id in visited:
                continue
            visited.add(current_id)

            deps = db.query(Dependency).filter(Dependency.downstream_id == current_id).all()
            for dep in deps:
                if dep.upstream_id not in visited:
                    upstream = db.query(ProbeTarget).filter(ProbeTarget.id == dep.upstream_id).first()
                    if upstream:
                        result.append(upstream)
                        queue.append(dep.upstream_id)

        return result

    def _update_cascade_status(self, db: Session, upstream_target: ProbeTarget):
        if upstream_target.status == "down" or upstream_target.status == "degraded":
            downstream_targets = self._get_downstream_targets(db, upstream_target.id)
            for target in downstream_targets:
                if not target.cascade_affected:
                    target.cascade_affected = True
                    target.cascade_source_id = upstream_target.id
                    if not target.paused:
                        target.paused = True
                        self.remove_target(target.id)
                    db.flush()
                    db.refresh(target)
                    self._notify_status_change(target)
        else:
            downstream_targets = self._get_downstream_targets(db, upstream_target.id)
            for target in downstream_targets:
                upstreams = self._get_upstream_targets(db, target.id)
                has_failed_upstream = any(
                    u.status in ("down", "degraded") for u in upstreams
                )
                if not has_failed_upstream and target.cascade_affected:
                    target.cascade_affected = False
                    target.cascade_source_id = None
                    if target.paused:
                        target.paused = False
                        self._start_target_task_sync(target.id)
                    db.flush()
                    db.refresh(target)
                    self._notify_status_change(target)

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

            in_silent = self._is_in_silent_window(target)
            if not target.silenced and not in_silent:
                self._notify_alert(target, alert)

            self._update_cascade_status(db, target)

        self._notify_status_change(target)

    def _get_effective_thresholds(self, target: ProbeTarget) -> dict:
        degrade_threshold = 2
        down_threshold = 5
        success_threshold = 3

        if target.group:
            degrade_threshold = target.group.degrade_threshold or 2
            down_threshold = target.group.down_threshold or 5
            success_threshold = target.group.success_threshold or 3

        if target.degrade_threshold is not None:
            degrade_threshold = target.degrade_threshold
        if target.down_threshold is not None:
            down_threshold = target.down_threshold
        if target.success_threshold is not None:
            success_threshold = target.success_threshold

        return {
            "degrade": degrade_threshold,
            "down": down_threshold,
            "success": success_threshold
        }

    def _get_effective_strategy(self, target: ProbeTarget) -> dict:
        adaptive_enabled = False
        slow_interval = 60
        fast_interval = 5
        silent_start = None
        silent_end = None

        if target.group:
            adaptive_enabled = target.group.adaptive_enabled or False
            slow_interval = target.group.slow_interval or 60
            fast_interval = target.group.fast_interval or 5
            silent_start = target.group.silent_start
            silent_end = target.group.silent_end

        if target.adaptive_enabled is not None:
            adaptive_enabled = target.adaptive_enabled
        if target.slow_interval is not None:
            slow_interval = target.slow_interval
        if target.fast_interval is not None:
            fast_interval = target.fast_interval
        if target.silent_start is not None:
            silent_start = target.silent_start
        if target.silent_end is not None:
            silent_end = target.silent_end

        return {
            "adaptive_enabled": adaptive_enabled,
            "slow_interval": slow_interval,
            "fast_interval": fast_interval,
            "silent_start": silent_start,
            "silent_end": silent_end
        }

    def _is_in_silent_window(self, target: ProbeTarget) -> bool:
        strategy = self._get_effective_strategy(target)
        silent_start = strategy["silent_start"]
        silent_end = strategy["silent_end"]

        if not silent_start or not silent_end:
            return False

        try:
            now = datetime.utcnow()
            current_time = now.strftime("%H:%M")

            start_h, start_m = map(int, silent_start.split(":"))
            end_h, end_m = map(int, silent_end.split(":"))
            now_h, now_m = now.hour, now.minute

            start_total = start_h * 60 + start_m
            end_total = end_h * 60 + end_m
            now_total = now_h * 60 + now_m

            if start_total <= end_total:
                return start_total <= now_total <= end_total
            else:
                return now_total >= start_total or now_total <= end_total
        except Exception:
            return False

    def _get_sleep_until_silent_end(self, target: ProbeTarget) -> int:
        strategy = self._get_effective_strategy(target)
        silent_end = strategy["silent_end"]

        if not silent_end:
            return 60

        try:
            now = datetime.utcnow()
            end_h, end_m = map(int, silent_end.split(":"))

            end_time = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
            if end_time <= now:
                end_time += timedelta(days=1)

            sleep_seconds = (end_time - now).total_seconds()
            return max(1, int(sleep_seconds))
        except Exception:
            return 60

    def _get_effective_interval(self, target: ProbeTarget) -> int:
        strategy = self._get_effective_strategy(target)

        if not strategy["adaptive_enabled"]:
            interval = target.interval
            self._interval_cache[target.id] = interval
            return interval

        status = target.status

        if status == "healthy" and target.consecutive_failures == 0:
            interval = strategy["slow_interval"]
        elif status == "down":
            interval = strategy["slow_interval"]
        else:
            interval = strategy["fast_interval"]

        self._interval_cache[target.id] = interval
        return interval

    def _get_cached_interval(self, target_id: int) -> Optional[int]:
        return self._interval_cache.get(target_id)

    def _calculate_status(self, target: ProbeTarget, current_status: str) -> str:
        thresholds = self._get_effective_thresholds(target)

        if target.consecutive_successes >= thresholds["success"]:
            return "healthy"

        if target.consecutive_failures == 0:
            return current_status

        if current_status == "healthy":
            if target.consecutive_failures >= thresholds["degrade"]:
                return "degraded"
            return current_status
        elif current_status == "degraded":
            if target.consecutive_failures >= thresholds["down"]:
                return "down"
            return current_status
        elif current_status == "down":
            return "down"

        return current_status

    def _notify_status_change(self, target: ProbeTarget, current_interval: int = None, next_probe_at: datetime = None, in_silent_window: bool = False):
        if current_interval is None:
            current_interval = self._get_effective_interval(target)
        if next_probe_at is None:
            next_probe_at = datetime.utcnow() + timedelta(seconds=current_interval)

        strategy = self._get_effective_strategy(target)

        cascade_source_name = None
        if target.cascade_source_id and target.cascade_source:
            cascade_source_name = target.cascade_source.name

        rule_name = None
        if target.rule_id and target.rule:
            rule_name = target.rule.name

        data = {
            "type": "status_update",
            "target": {
                "id": target.id,
                "group_id": target.group_id,
                "rule_id": target.rule_id,
                "rule_name": rule_name,
                "name": target.name,
                "type": target.type,
                "address": target.address,
                "status": target.status,
                "paused": target.paused,
                "silenced": target.silenced,
                "cascade_affected": target.cascade_affected,
                "cascade_source_id": target.cascade_source_id,
                "cascade_source_name": cascade_source_name,
                "consecutive_failures": target.consecutive_failures,
                "consecutive_successes": target.consecutive_successes,
                "last_check": target.last_check.isoformat() if target.last_check else None,
                "interval": target.interval,
                "adaptive_enabled": strategy["adaptive_enabled"],
                "slow_interval": strategy["slow_interval"],
                "fast_interval": strategy["fast_interval"],
                "silent_start": strategy["silent_start"],
                "silent_end": strategy["silent_end"],
                "current_interval": current_interval,
                "next_probe_at": next_probe_at.isoformat(),
                "in_silent_window": in_silent_window
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
                "timestamp": result["timestamp"].isoformat() if isinstance(result["timestamp"], datetime) else result["timestamp"],
                "success": result["success"],
                "latency_ms": result["latency_ms"],
                "error_message": result["error_message"],
                "has_rule": target.rule_id is not None,
                "step_results": result.get("step_results", []),
                "rule_execution_id": result.get("rule_execution_id"),
            }
        }
        for callback in self.result_callbacks:
            try:
                callback(data)
            except Exception as e:
                print(f"Result callback error: {e}")


probe_engine = ProbeEngine()
