import asyncio
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from sqlalchemy.orm import Session
import httpx
import socket

from .database import SessionLocal
from .models import (
    ProbeTarget, ObservationPoint, TargetObserverBinding,
    ObserverProbeResult, Alert
)


OBSERVER_HEARTBEAT_TIMEOUT = 300


class ObserverEngine:
    def __init__(self):
        self.running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self.status_callbacks: List[Callable] = []
        self._simulation_mode = True
        self._simulated_states: Dict[int, Dict] = {}

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def register_status_callback(self, callback: Callable):
        self.status_callbacks.append(callback)

    async def start(self):
        self.running = True
        self._loop = asyncio.get_running_loop()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor_loop())
        self._init_simulated_states()

    async def stop(self):
        self.running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

    def _init_simulated_states(self):
        db = SessionLocal()
        try:
            observers = db.query(ObservationPoint).all()
            targets = db.query(ProbeTarget).all()
            for target in targets:
                if target.id not in self._simulated_states:
                    self._simulated_states[target.id] = {
                        "global_failure": False,
                        "partial_fail_regions": [],
                        "observer_offline_ids": [],
                    }
        finally:
            db.close()

    def set_target_simulation_state(self, target_id: int, state: dict):
        self._simulated_states[target_id] = state

    async def _heartbeat_monitor_loop(self):
        while self.running:
            try:
                self._check_observer_heartbeats()
            except Exception as e:
                print(f"Heartbeat monitor error: {e}")
            await asyncio.sleep(10)

    def _check_observer_heartbeats(self):
        db = SessionLocal()
        try:
            now = datetime.utcnow()
            observers = db.query(ObservationPoint).all()
            changed = False
            for observer in observers:
                if observer.last_heartbeat:
                    offline_threshold = now - timedelta(seconds=OBSERVER_HEARTBEAT_TIMEOUT)
                    should_be_offline = observer.last_heartbeat < offline_threshold
                    if observer.status == "online" and should_be_offline:
                        observer.status = "offline"
                        changed = True
                        self._handle_observer_offline(db, observer)
                    elif observer.status == "offline" and not should_be_offline:
                        observer.status = "online"
                        changed = True
                        self._handle_observer_back_online(db, observer)
            if changed:
                db.commit()
                self._broadcast_observers_update()
        finally:
            db.close()

    def _handle_observer_offline(self, db: Session, observer: ObservationPoint):
        print(f"Observer '{observer.name}' (id={observer.id}) went offline - tasks will be transferred")
        self._broadcast_observers_update()

    def _handle_observer_back_online(self, db: Session, observer: ObservationPoint):
        print(f"Observer '{observer.name}' (id={observer.id}) came back online - tasks will be restored")
        observer.last_heartbeat = datetime.utcnow()
        self._broadcast_observers_update()

    def heartbeat(self, observer_id: int):
        db = SessionLocal()
        try:
            observer = db.query(ObservationPoint).filter(
                ObservationPoint.id == observer_id
            ).first()
            if observer:
                observer.last_heartbeat = datetime.utcnow()
                if observer.status == "offline":
                    observer.status = "online"
                    self._handle_observer_back_online(db, observer)
                db.commit()
                self._broadcast_observers_update()
                return True
            return False
        finally:
            db.close()

    def get_target_observers(self, db: Session, target_id: int) -> List[ObservationPoint]:
        bindings = db.query(TargetObserverBinding).filter(
            TargetObserverBinding.target_id == target_id
        ).all()
        observer_ids = [b.observer_id for b in bindings]
        if not observer_ids:
            return db.query(ObservationPoint).filter(
                ObservationPoint.status == "online"
            ).all()
        return db.query(ObservationPoint).filter(
            ObservationPoint.id.in_(observer_ids)
        ).all()

    def get_effective_observers(self, db: Session, target_id: int) -> List[ObservationPoint]:
        observers = self.get_target_observers(db, target_id)
        offline_ids = [o.id for o in observers if o.status == "offline"]
        online_observers = [o for o in observers if o.status == "online"]
        if not online_observers:
            all_online = db.query(ObservationPoint).filter(
                ObservationPoint.status == "online"
            ).all()
            return all_online
        if offline_ids:
            all_online = db.query(ObservationPoint).filter(
                ObservationPoint.status == "online"
            ).all()
            extra_needed = len(offline_ids)
            existing_ids = {o.id for o in online_observers}
            for extra in all_online:
                if extra.id not in existing_ids and extra_needed > 0:
                    online_observers.append(extra)
                    extra_needed -= 1
        return online_observers

    async def execute_coordinated_probe(self, target: ProbeTarget) -> dict:
        db = SessionLocal()
        try:
            round_id = f"rnd_{uuid.uuid4().hex[:12]}"

            if self._simulation_mode:
                now = datetime.utcnow()
                keep_offline_ids = set()
                state = self._simulated_states.get(target.id, {})
                for oid in state.get("observer_offline_ids", []):
                    keep_offline_ids.add(oid)

                all_observers = db.query(ObservationPoint).all()
                for obs in all_observers:
                    if obs.status == "online" and obs.id not in keep_offline_ids:
                        obs.last_heartbeat = now
                    elif obs.status == "offline" and obs.id not in keep_offline_ids:
                        if obs.last_heartbeat and (now - obs.last_heartbeat).total_seconds() < OBSERVER_HEARTBEAT_TIMEOUT:
                            obs.status = "online"
                            obs.last_heartbeat = now
                db.flush()

            all_assigned = self.get_target_observers(db, target.id)
            effective_observers = self.get_effective_observers(db, target.id)

            assigned_ids = {o.id for o in all_assigned}
            effective_ids = {o.id for o in effective_observers}
            transferred_ids = effective_ids - assigned_ids
            offline_assigned = [o for o in all_assigned if o.status == "offline" or o.id not in effective_ids]

            if not effective_observers:
                full_results = []
                for obs in all_assigned:
                    full_results.append({
                        "observer_id": obs.id,
                        "observer_name": obs.name,
                        "observer_region": obs.region,
                        "observer_status": "offline",
                        "success": False,
                        "latency_ms": None,
                        "error_message": "Observer offline - no available observers to transfer task",
                        "round_id": round_id,
                        "is_transferred": False,
                    })
                return {
                    "success": False,
                    "latency_ms": 0,
                    "error_message": "No available observation points",
                    "timestamp": datetime.utcnow(),
                    "round_id": round_id,
                    "observer_results": full_results,
                    "unified_status": "unknown",
                    "failure_count": 0,
                    "success_count": 0,
                    "offline_count": len(all_assigned),
                    "online_count": 0,
                }

            transferred_observers = [o for o in effective_observers if o.id in transferred_ids]
            original_online = [o for o in effective_observers if o.id in assigned_ids]

            tasks = []
            task_observer_map = []
            for observer in original_online:
                tasks.append(self._probe_from_observer(target, observer, round_id))
                task_observer_map.append((observer, False))
            for observer in transferred_observers:
                tasks.append(self._probe_from_observer(target, observer, round_id))
                task_observer_map.append((observer, True))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            executed_results = []
            for i, res in enumerate(results):
                observer, is_transferred = task_observer_map[i]
                if isinstance(res, Exception):
                    executed_results.append({
                        "observer_id": observer.id,
                        "observer_name": observer.name,
                        "observer_region": observer.region,
                        "observer_status": "online",
                        "success": False,
                        "latency_ms": None,
                        "error_message": str(res),
                        "round_id": round_id,
                        "is_transferred": is_transferred,
                    })
                else:
                    res["observer_status"] = "online"
                    res["is_transferred"] = is_transferred
                    executed_results.append(res)

            full_results = []
            executed_by_id = {r["observer_id"]: r for r in executed_results}

            for obs in all_assigned:
                if obs.id in executed_by_id:
                    r = executed_by_id[obs.id]
                    full_results.append(r)
                else:
                    full_results.append({
                        "observer_id": obs.id,
                        "observer_name": obs.name,
                        "observer_region": obs.region,
                        "observer_status": "offline",
                        "success": False,
                        "latency_ms": None,
                        "error_message": "Observer offline - task transferred",
                        "round_id": round_id,
                        "is_transferred": False,
                    })

            for r in executed_results:
                if r.get("is_transferred"):
                    full_results.append(r)

            for orr in full_results:
                db_result = ObserverProbeResult(
                    target_id=target.id,
                    observer_id=orr["observer_id"],
                    round_id=round_id,
                    timestamp=datetime.utcnow(),
                    success=orr["success"],
                    latency_ms=orr["latency_ms"],
                    error_message=orr["error_message"],
                )
                db.add(db_result)

            online_results = [r for r in full_results if r.get("observer_status") == "online"]
            online_count = len(online_results)
            success_count = sum(1 for r in online_results if r["success"])
            failure_count = online_count - success_count
            offline_count = len([r for r in full_results if r.get("observer_status") == "offline"])

            unified_status = self._calculate_unified_status(
                success_count, failure_count, online_count
            )

            avg_latency = None
            latencies = [r["latency_ms"] for r in online_results if r["success"] and r["latency_ms"] is not None]
            if latencies:
                avg_latency = sum(latencies) / len(latencies)

            db.commit()

            error_msg = None
            if unified_status in ("degraded", "down", "partial"):
                failed_regions = [
                    f"{r['observer_region']}({r['observer_name']})"
                    for r in online_results if not r["success"]
                ]
                if failed_regions:
                    error_msg = f"Failed from: {', '.join(failed_regions)}"
                else:
                    error_msg = "Some observers offline"

            return {
                "success": unified_status != "down",
                "latency_ms": avg_latency,
                "error_message": error_msg,
                "timestamp": datetime.utcnow(),
                "round_id": round_id,
                "observer_results": full_results,
                "unified_status": unified_status,
                "success_count": success_count,
                "failure_count": failure_count,
                "offline_count": offline_count,
                "online_count": online_count,
            }
        finally:
            db.close()

    def _calculate_unified_status(self, success_count: int, failure_count: int, total_online: int) -> str:
        if total_online == 0:
            return "unknown"
        failure_ratio = failure_count / total_online
        if failure_ratio > 0.5:
            return "down"
        elif failure_ratio > 0.2:
            return "degraded"
        elif failure_ratio > 0:
            return "partial"
        else:
            return "healthy"

    async def _probe_from_observer(self, target: ProbeTarget, observer: ObservationPoint, round_id: str) -> dict:
        if self._simulation_mode:
            return await self._simulated_probe(target, observer, round_id)

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

        if latency_ms is None:
            latency_ms = (time.time() - start_time) * 1000

        return {
            "observer_id": observer.id,
            "observer_name": observer.name,
            "observer_region": observer.region,
            "success": success,
            "latency_ms": latency_ms,
            "error_message": error_message,
            "round_id": round_id,
        }

    async def _simulated_probe(self, target: ProbeTarget, observer: ObservationPoint, round_id: str) -> dict:
        state = self._simulated_states.get(target.id, {})
        base_latency = {
            "华北": 30,
            "华东": 25,
            "华南": 35,
            "西南": 50,
            "海外-新加坡": 120,
            "海外-美国": 200,
        }.get(observer.region, 40)

        import random
        latency_jitter = random.uniform(-5, 15)
        latency_ms = base_latency + latency_jitter

        if observer.status == "offline" or observer.id in state.get("observer_offline_ids", []):
            return {
                "observer_id": observer.id,
                "observer_name": observer.name,
                "observer_region": observer.region,
                "success": False,
                "latency_ms": None,
                "error_message": "Observer offline",
                "round_id": round_id,
            }

        if state.get("global_failure"):
            return {
                "observer_id": observer.id,
                "observer_name": observer.name,
                "observer_region": observer.region,
                "success": False,
                "latency_ms": latency_ms * 3,
                "error_message": "Service unavailable (simulated global failure)",
                "round_id": round_id,
            }

        if observer.region in state.get("partial_fail_regions", []):
            return {
                "observer_id": observer.id,
                "observer_name": observer.name,
                "observer_region": observer.region,
                "success": False,
                "latency_ms": latency_ms * 2,
                "error_message": f"Region {observer.region} access failed (simulated regional failure)",
                "round_id": round_id,
            }

        return {
            "observer_id": observer.id,
            "observer_name": observer.name,
            "observer_region": observer.region,
            "success": True,
            "latency_ms": latency_ms,
            "error_message": None,
            "round_id": round_id,
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

    def _broadcast_observers_update(self):
        db = SessionLocal()
        try:
            observers = db.query(ObservationPoint).all()
            data = {
                "type": "observers_update",
                "observers": [
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
            }
            for callback in self.status_callbacks:
                try:
                    callback(data)
                except Exception as e:
                    print(f"Observer broadcast error: {e}")
        finally:
            db.close()

    def get_matrix_data(self, region_filter: Optional[str] = None) -> dict:
        db = SessionLocal()
        try:
            observers_query = db.query(ObservationPoint)
            if region_filter:
                observers_query = observers_query.filter(ObservationPoint.region == region_filter)
            observers = observers_query.order_by(ObservationPoint.region, ObservationPoint.name).all()

            targets = db.query(ProbeTarget).order_by(ProbeTarget.id).all()

            observer_ids = [o.id for o in observers]
            target_ids = [t.id for t in targets]

            cells = []
            for target in targets:
                latest_by_observer = {}
                results = db.query(ObserverProbeResult).filter(
                    ObserverProbeResult.target_id == target.id,
                    ObserverProbeResult.observer_id.in_(observer_ids)
                ).order_by(ObserverProbeResult.timestamp.desc()).limit(len(observers) * 5).all()

                for r in results:
                    if r.observer_id not in latest_by_observer:
                        latest_by_observer[r.observer_id] = r

                for observer in observers:
                    latest = latest_by_observer.get(observer.id)
                    cell = {
                        "target_id": target.id,
                        "target_name": target.name,
                        "target_status": target.status,
                        "observer_id": observer.id,
                        "observer_name": observer.name,
                        "observer_region": observer.region,
                        "observer_status": observer.status,
                    }
                    if latest:
                        cell.update({
                            "latest_status": "success" if latest.success else "failed",
                            "latest_latency": latest.latency_ms,
                            "latest_timestamp": latest.timestamp.isoformat(),
                            "error_message": latest.error_message,
                        })
                    else:
                        cell.update({
                            "latest_status": "pending",
                            "latest_latency": None,
                            "latest_timestamp": None,
                            "error_message": None,
                        })
                    cells.append(cell)

            regions = list({o.region for o in db.query(ObservationPoint).all()})
            regions.sort()

            return {
                "observers": [
                    {
                        "id": o.id,
                        "name": o.name,
                        "region": o.region,
                        "status": o.status,
                    }
                    for o in observers
                ],
                "targets": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "status": t.status,
                        "group_id": t.group_id,
                    }
                    for t in targets
                ],
                "cells": cells,
                "regions": regions,
            }
        finally:
            db.close()

    def get_target_round_history(self, target_id: int, limit: int = 20) -> list:
        db = SessionLocal()
        try:
            results = db.query(ObserverProbeResult).filter(
                ObserverProbeResult.target_id == target_id
            ).order_by(ObserverProbeResult.timestamp.desc()).limit(limit * 10).all()

            rounds = {}
            for r in results:
                if r.round_id not in rounds:
                    rounds[r.round_id] = {
                        "round_id": r.round_id,
                        "timestamp": r.timestamp,
                        "results": [],
                    }
                rounds[r.round_id]["results"].append(r)

            round_list = sorted(rounds.values(), key=lambda x: x["timestamp"], reverse=True)[:limit]

            summary_list = []
            for round_data in round_list:
                round_results = round_data["results"]
                observers = db.query(ObservationPoint).filter(
                    ObservationPoint.id.in_([r.observer_id for r in round_results])
                ).all()
                observer_map = {o.id: o for o in observers}

                success_count = sum(1 for r in round_results if r.success)
                failure_count = sum(1 for r in round_results if not r.success)
                online_count = len(round_results)

                detailed_results = []
                for r in round_results:
                    obs = observer_map.get(r.observer_id)
                    detailed_results.append({
                        "id": r.id,
                        "observer_id": r.observer_id,
                        "observer_name": obs.name if obs else f"Unknown({r.observer_id})",
                        "observer_region": obs.region if obs else "Unknown",
                        "observer_status": obs.status if obs else "unknown",
                        "success": r.success,
                        "latency_ms": r.latency_ms,
                        "error_message": r.error_message,
                        "timestamp": r.timestamp.isoformat(),
                    })

                failure_type = self._classify_failure_type(
                    success_count, failure_count, online_count, detailed_results
                )

                summary_list.append({
                    "round_id": round_data["round_id"],
                    "timestamp": round_data["timestamp"].isoformat(),
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "online_count": online_count,
                    "unified_status": self._calculate_unified_status(
                        success_count, failure_count, online_count
                    ),
                    "failure_type": failure_type,
                    "results": detailed_results,
                })

            return summary_list
        finally:
            db.close()

    def _classify_failure_type(self, success_count, failure_count, online_count, results) -> str:
        if failure_count == 0:
            return "all_healthy"
        if online_count == 0:
            return "all_observers_offline"
        offline_count = sum(1 for r in results if r["observer_status"] == "offline")
        if offline_count > 0 and offline_count >= failure_count:
            return "observer_offline"
        failure_ratio = failure_count / online_count if online_count > 0 else 0
        if failure_ratio > 0.5:
            return "service_failure"
        failed_regions = {r["observer_region"] for r in results if not r["success"]}
        if len(failed_regions) == 1:
            return "regional_failure"
        return "partial_failure"


observer_engine = ObserverEngine()
