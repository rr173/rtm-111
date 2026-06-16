import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import (
    ProbeTarget, RegistrySource, SyncEvent, SyncEventDetail,
)
from .probe_engine import probe_engine


class SyncEngine:
    def __init__(self):
        self.running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._sync_tasks: Dict[int, asyncio.Task] = {}
        self._sync_callback = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def register_sync_callback(self, callback):
        self._sync_callback = callback

    async def start(self):
        self.running = True
        self._loop = asyncio.get_running_loop()
        db = SessionLocal()
        try:
            sources = db.query(RegistrySource).filter(RegistrySource.enabled == True).all()
            for source in sources:
                self._schedule_source(source.id)
        finally:
            db.close()

    async def stop(self):
        self.running = False
        for task in list(self._sync_tasks.values()):
            task.cancel()
        self._sync_tasks.clear()

    def add_source(self, source_id: int):
        if source_id not in self._sync_tasks:
            self._schedule_source(source_id)

    def remove_source(self, source_id: int):
        if source_id in self._sync_tasks:
            task = self._sync_tasks[source_id]
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(task.cancel)
            del self._sync_tasks[source_id]

    def update_source(self, source_id: int):
        self.remove_source(source_id)
        db = SessionLocal()
        try:
            source = db.query(RegistrySource).filter(RegistrySource.id == source_id).first()
            if source and source.enabled:
                self.add_source(source_id)
        finally:
            db.close()

    def _schedule_source(self, source_id: int):
        if self._loop is None:
            return
        if self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._run_source_loop(source_id), self._loop
            )

    async def _run_source_loop(self, source_id: int):
        await asyncio.sleep(5)
        while self.running:
            db = SessionLocal()
            try:
                source = db.query(RegistrySource).filter(RegistrySource.id == source_id).first()
                if not source or not source.enabled:
                    break
                interval = source.pull_interval
            finally:
                db.close()

            try:
                await self.sync_source(source_id, triggered_by="auto")
            except Exception as e:
                print(f"Auto sync error for source {source_id}: {e}")

            await asyncio.sleep(interval)

    async def sync_source(self, source_id: int, triggered_by: str = "manual") -> dict:
        db = SessionLocal()
        try:
            source = db.query(RegistrySource).filter(RegistrySource.id == source_id).first()
            if not source:
                return {"error": "Source not found"}

            sync_event = SyncEvent(
                source_id=source_id,
                triggered_by=triggered_by,
                status="running",
                started_at=datetime.utcnow(),
            )
            db.add(sync_event)
            db.commit()
            db.refresh(sync_event)

            try:
                services = await self._fetch_services(source)
                result = self._process_sync(db, source, sync_event, services)

                sync_event.status = "success"
                sync_event.finished_at = datetime.utcnow()
                sync_event.discovered_count = result["discovered_count"]
                sync_event.new_count = result["new_count"]
                sync_event.deprecated_count = result["deprecated_count"]
                sync_event.failed_count = result["failed_count"]
                sync_event.unchanged_count = result["unchanged_count"]
                sync_event.raw_service_count = result["raw_service_count"]

                source.last_sync_at = datetime.utcnow()
                source.last_sync_status = "success"

                db.commit()

                if self._sync_callback:
                    self._sync_callback({
                        "source_id": source_id,
                        "event_id": sync_event.id,
                        "result": result,
                    })

                return result
            except Exception as e:
                sync_event.status = "failed"
                sync_event.finished_at = datetime.utcnow()
                sync_event.error_message = str(e)
                source.last_sync_at = datetime.utcnow()
                source.last_sync_status = "failed"
                db.commit()

                if self._sync_callback:
                    self._sync_callback({
                        "source_id": source_id,
                        "event_id": sync_event.id,
                        "error": str(e),
                    })

                return {"error": str(e)}
        finally:
            db.close()

    async def _fetch_services(self, source: RegistrySource) -> List[dict]:
        headers = source.headers or {}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(source.url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ["services", "data", "items", "results", "targets"]:
                if key in data and isinstance(data[key], list):
                    return data[key]
            return [data]

        return []

    def _normalize_service(self, svc: dict) -> Optional[dict]:
        if not isinstance(svc, dict):
            return None

        name = svc.get("name") or svc.get("service_name") or svc.get("serviceName") or svc.get("id") or svc.get("host")
        address = svc.get("address") or svc.get("url") or svc.get("endpoint") or svc.get("host") or svc.get("addr")

        if not name:
            return None

        if not address:
            address = name

        svc_type = svc.get("type") or svc.get("probe_type") or svc.get("protocol") or "http"
        if svc_type not in ("http", "tcp"):
            svc_type = "http"

        return {
            "name": str(name),
            "address": str(address),
            "type": svc_type,
        }

    def _process_sync(self, db: Session, source: RegistrySource, sync_event: SyncEvent, raw_services: List[dict]) -> dict:
        now = datetime.utcnow()
        discovered = []
        new_count = 0
        deprecated_count = 0
        failed_count = 0
        unchanged_count = 0

        for raw_svc in raw_services:
            svc = self._normalize_service(raw_svc)
            if not svc:
                failed_count += 1
                continue
            discovered.append(svc)

        discovered_addresses = {s["address"] for s in discovered}
        discovered_by_address = {s["address"]: s for s in discovered}

        existing_targets = db.query(ProbeTarget).filter(
            ProbeTarget.source_id == source.id
        ).all()
        existing_by_address = {t.address: t for t in existing_targets}

        for svc in discovered:
            existing = existing_by_address.get(svc["address"])
            if existing:
                existing.last_seen_at = now
                if existing.deprecated:
                    existing.deprecated = False
                    existing.deprecated_at = None
                    existing.paused = False
                    probe_engine.add_target(existing.id)

                    db.add(SyncEventDetail(
                        event_id=sync_event.id,
                        target_id=existing.id,
                        service_name=svc["name"],
                        service_address=svc["address"],
                        action="restored",
                        detail=f"服务重新上线，目标已恢复为活跃状态",
                    ))
                    new_count += 1
                else:
                    unchanged_count += 1
            else:
                target = ProbeTarget(
                    name=svc["name"],
                    type=source.default_type if source.default_type else svc["type"],
                    address=svc["address"],
                    group_id=source.default_group_id,
                    interval=source.default_interval,
                    timeout=source.default_timeout,
                    source_id=source.id,
                    deprecated=False,
                    last_seen_at=now,
                    status="healthy",
                    consecutive_successes=0,
                    consecutive_failures=0,
                )
                db.add(target)
                db.flush()

                probe_engine.add_target(target.id)

                db.add(SyncEventDetail(
                    event_id=sync_event.id,
                    target_id=target.id,
                    service_name=svc["name"],
                    service_address=svc["address"],
                    action="created",
                    detail=f"新服务自动创建，类型={target.type}，间隔={target.interval}s，超时={target.timeout}s",
                ))
                new_count += 1

        deprecate_threshold = now - timedelta(hours=source.deprecate_after_hours)
        for address, target in existing_by_address.items():
            if address not in discovered_addresses and not target.deprecated:
                if target.last_seen_at and target.last_seen_at < deprecate_threshold:
                    target.deprecated = True
                    target.deprecated_at = now
                    target.paused = True
                    probe_engine.toggle_target(target.id, True)

                    db.add(SyncEventDetail(
                        event_id=sync_event.id,
                        target_id=target.id,
                        service_name=target.name,
                        service_address=target.address,
                        action="deprecated",
                        detail=f"服务已消失超过{source.deprecate_after_hours}小时，标记为废弃并停止探测",
                    ))
                    deprecated_count += 1
                elif not target.last_seen_at:
                    target.last_seen_at = now
                    unchanged_count += 1

        db.commit()

        return {
            "discovered_count": len(discovered),
            "new_count": new_count,
            "deprecated_count": deprecated_count,
            "failed_count": failed_count,
            "unchanged_count": unchanged_count,
            "raw_service_count": len(raw_services),
        }

    def restore_target(self, target_id: int) -> dict:
        db = SessionLocal()
        try:
            target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
            if not target:
                return {"error": "Target not found"}

            target.deprecated = False
            target.deprecated_at = None
            target.paused = False
            target.last_seen_at = datetime.utcnow()
            db.commit()

            probe_engine.toggle_target(target.id, False)

            return {"message": "Target restored", "target_id": target_id}
        finally:
            db.close()


sync_engine = SyncEngine()
