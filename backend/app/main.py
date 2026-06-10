from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Set
from datetime import datetime, timedelta
from collections import deque

from .database import engine, get_db, Base
from .models import ProbeTarget, ProbeResult, Alert, ProbeGroup, Dependency
from .schemas import (
    ProbeTargetCreate, ProbeTargetUpdate, ProbeTargetResponse,
    ProbeResultResponse, AlertResponse, AlertAcknowledge,
    ProbeGroupCreate, ProbeGroupUpdate, ProbeGroupResponse,
    ProbeGroupWithTargetsResponse,
    DependencyCreate, DependencyUpdate, DependencyResponse,
    DependencyWithNamesResponse, CascadeSimulationResponse
)
from .probe_engine import probe_engine
from .websocket_manager import manager, get_target_history


def _enrich_target(target: ProbeTarget, db: Session = None) -> dict:
    strategy = probe_engine._get_effective_strategy(target)
    current_interval = probe_engine._get_effective_interval(target)
    in_silent = probe_engine._is_in_silent_window(target)
    next_probe_at = datetime.utcnow() + timedelta(seconds=current_interval)

    cascade_source_name = None
    if target.cascade_source_id and target.cascade_source:
        cascade_source_name = target.cascade_source.name
    elif target.cascade_source_id and db:
        source = db.query(ProbeTarget).filter(ProbeTarget.id == target.cascade_source_id).first()
        if source:
            cascade_source_name = source.name

    return {
        "id": target.id,
        "group_id": target.group_id,
        "name": target.name,
        "type": target.type,
        "address": target.address,
        "interval": target.interval,
        "timeout": target.timeout,
        "expected_status": target.expected_status,
        "paused": target.paused,
        "silenced": target.silenced,
        "status": target.status,
        "cascade_affected": target.cascade_affected,
        "cascade_source_id": target.cascade_source_id,
        "cascade_source_name": cascade_source_name,
        "consecutive_failures": target.consecutive_failures,
        "consecutive_successes": target.consecutive_successes,
        "last_check": target.last_check,
        "degrade_threshold": target.degrade_threshold,
        "down_threshold": target.down_threshold,
        "success_threshold": target.success_threshold,
        "adaptive_enabled": strategy["adaptive_enabled"],
        "slow_interval": strategy["slow_interval"],
        "fast_interval": strategy["fast_interval"],
        "silent_start": strategy["silent_start"],
        "silent_end": strategy["silent_end"],
        "current_interval": current_interval,
        "next_probe_at": next_probe_at,
        "in_silent_window": in_silent,
        "created_at": target.created_at,
    }

Base.metadata.create_all(bind=engine)


def _migrate_database():
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            result = conn.execute(text("PRAGMA table_info(probe_groups)"))
            columns = [row[1] for row in result.fetchall()]

            group_new_columns = [
                ("adaptive_enabled", "INTEGER DEFAULT 0"),
                ("slow_interval", "INTEGER DEFAULT 60"),
                ("fast_interval", "INTEGER DEFAULT 5"),
                ("silent_start", "VARCHAR(5)"),
                ("silent_end", "VARCHAR(5)"),
            ]
            for col_name, col_def in group_new_columns:
                if col_name not in columns:
                    conn.execute(text(f"ALTER TABLE probe_groups ADD COLUMN {col_name} {col_def}"))
                    print(f"Added column {col_name} to probe_groups")

            result = conn.execute(text("PRAGMA table_info(probe_targets)"))
            columns = [row[1] for row in result.fetchall()]

            target_new_columns = [
                ("adaptive_enabled", "INTEGER DEFAULT 0"),
                ("slow_interval", "INTEGER DEFAULT 60"),
                ("fast_interval", "INTEGER DEFAULT 5"),
                ("silent_start", "VARCHAR(5)"),
                ("silent_end", "VARCHAR(5)"),
                ("cascade_affected", "INTEGER DEFAULT 0"),
                ("cascade_source_id", "INTEGER"),
            ]
            for col_name, col_def in target_new_columns:
                if col_name not in columns:
                    conn.execute(text(f"ALTER TABLE probe_targets ADD COLUMN {col_name} {col_def}"))
                    print(f"Added column {col_name} to probe_targets")

            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='dependencies'"))
            if not result.fetchone():
                conn.execute(text("""
                    CREATE TABLE dependencies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        upstream_id INTEGER NOT NULL,
                        downstream_id INTEGER NOT NULL,
                        description VARCHAR(255),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (upstream_id) REFERENCES probe_targets(id) ON DELETE CASCADE,
                        FOREIGN KEY (downstream_id) REFERENCES probe_targets(id) ON DELETE CASCADE
                    )
                """))
                conn.execute(text("CREATE INDEX idx_dependencies_upstream ON dependencies(upstream_id)"))
                conn.execute(text("CREATE INDEX idx_dependencies_downstream ON dependencies(downstream_id)"))
                print("Created dependencies table")

            conn.commit()
        except Exception as e:
            print(f"Migration error: {e}")


_migrate_database()

app = FastAPI(title="Probe Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    import asyncio
    loop = asyncio.get_running_loop()
    probe_engine.set_loop(loop)
    manager.set_loop(loop)
    _init_demo_data()
    await probe_engine.start()


@app.on_event("shutdown")
async def shutdown_event():
    await probe_engine.stop()


def _init_demo_data():
    db = next(get_db())
    try:
        target_count = db.query(ProbeTarget).count()
        group_count = db.query(ProbeGroup).count()
        if target_count > 0 and group_count > 0:
            return

        now = datetime.utcnow()

        group1 = ProbeGroup(
            name="生产环境",
            description="核心业务线生产环境服务",
            color="#ef4444",
            degrade_threshold=3,
            down_threshold=8,
            success_threshold=3,
            adaptive_enabled=True,
            slow_interval=60,
            fast_interval=5,
            silent_start="02:00",
            silent_end="06:00"
        )
        db.add(group1)
        db.flush()

        group2 = ProbeGroup(
            name="测试环境",
            description="测试环境服务，容忍度较高",
            color="#22c55e",
            degrade_threshold=5,
            down_threshold=10,
            success_threshold=2,
            adaptive_enabled=False,
            slow_interval=120,
            fast_interval=10
        )
        db.add(group2)
        db.flush()

        group3 = ProbeGroup(
            name="内部工具",
            description="内部工具和第三方依赖",
            color="#3b82f6",
            degrade_threshold=2,
            down_threshold=5,
            success_threshold=3,
            adaptive_enabled=True,
            slow_interval=120,
            fast_interval=15,
            silent_start="01:00",
            silent_end="05:00"
        )
        db.add(group3)
        db.flush()

        target1 = ProbeTarget(
            name="示例服务-健康",
            group_id=group1.id,
            type="http",
            address="https://httpbin.org/status/200",
            interval=10,
            timeout=5,
            expected_status="200",
            status="healthy",
            consecutive_successes=10,
            consecutive_failures=0,
            last_check=now
        )
        db.add(target1)
        db.flush()

        target2 = ProbeTarget(
            name="示例服务-间歇故障",
            group_id=group1.id,
            type="http",
            address="https://httpbin.org/status/200,500",
            interval=8,
            timeout=5,
            expected_status="200",
            status="degraded",
            consecutive_failures=3,
            consecutive_successes=0,
            last_check=now
        )
        db.add(target2)
        db.flush()

        target3 = ProbeTarget(
            name="示例服务-不可达",
            group_id=group2.id,
            type="tcp",
            address="192.0.2.1:9999",
            interval=15,
            timeout=3,
            expected_status=None,
            status="down",
            consecutive_failures=10,
            consecutive_successes=0,
            last_check=now
        )
        db.add(target3)
        db.flush()

        target4 = ProbeTarget(
            name="测试环境-API网关",
            group_id=group2.id,
            type="http",
            address="https://httpbin.org/status/200",
            interval=12,
            timeout=5,
            expected_status="200",
            status="healthy",
            consecutive_successes=5,
            consecutive_failures=0,
            last_check=now
        )
        db.add(target4)
        db.flush()

        target5 = ProbeTarget(
            name="内部文档服务",
            group_id=group3.id,
            type="http",
            address="https://httpbin.org/status/200",
            interval=30,
            timeout=10,
            expected_status="200",
            status="healthy",
            consecutive_successes=100,
            consecutive_failures=0,
            last_check=now
        )
        db.add(target5)
        db.flush()

        for i in range(20):
            t = now - timedelta(minutes=i * 2)
            db.add(ProbeResult(
                target_id=target1.id,
                timestamp=t,
                success=True,
                latency_ms=50 + i * 2 + (i % 3) * 10
            ))

        for i in range(20):
            t = now - timedelta(minutes=i * 2)
            success = i % 3 != 0
            db.add(ProbeResult(
                target_id=target2.id,
                timestamp=t,
                success=success,
                latency_ms=80 + i * 3 if success else None,
                error_message=None if success else "Status code mismatch: expected 200, got 500"
            ))

        for i in range(20):
            t = now - timedelta(minutes=i * 2)
            db.add(ProbeResult(
                target_id=target3.id,
                timestamp=t,
                success=False,
                latency_ms=3000,
                error_message="Connection timeout"
            ))

        for i in range(20):
            t = now - timedelta(minutes=i * 2)
            success = True
            db.add(ProbeResult(
                target_id=target4.id,
                timestamp=t,
                success=success,
                latency_ms=120 + i * 1.5 + (i % 4) * 8,
                error_message=None
            ))

        for i in range(20):
            t = now - timedelta(minutes=i * 2)
            success = i % 10 != 0
            db.add(ProbeResult(
                target_id=target5.id,
                timestamp=t,
                success=success,
                latency_ms=200 + i * 2 if success else None,
                error_message=None if success else "Service temporarily unavailable"
            ))

        db.add(Alert(
            target_id=target2.id,
            timestamp=now - timedelta(minutes=30),
            from_status="healthy",
            to_status="degraded",
            acknowledged=False
        ))
        db.add(Alert(
            target_id=target3.id,
            timestamp=now - timedelta(minutes=45),
            from_status="healthy",
            to_status="degraded",
            acknowledged=True,
            acknowledged_at=now - timedelta(minutes=40)
        ))
        db.add(Alert(
            target_id=target3.id,
            timestamp=now - timedelta(minutes=35),
            from_status="degraded",
            to_status="down",
            acknowledged=False
        ))

        dep1 = Dependency(
            upstream_id=target1.id,
            downstream_id=target2.id,
            description="示例服务依赖"
        )
        db.add(dep1)

        dep2 = Dependency(
            upstream_id=target2.id,
            downstream_id=target4.id,
            description="API网关依赖核心服务"
        )
        db.add(dep2)

        dep3 = Dependency(
            upstream_id=target4.id,
            downstream_id=target5.id,
            description="内部服务依赖API网关"
        )
        db.add(dep3)

        db.commit()
    except Exception as e:
        print(f"Demo data init error: {e}")
        db.rollback()
    finally:
        db.close()


@app.get("/api/groups", response_model=List[ProbeGroupResponse])
def list_groups(db: Session = Depends(get_db)):
    groups = db.query(ProbeGroup).order_by(ProbeGroup.id.asc()).all()
    return groups


@app.get("/api/groups/{group_id}", response_model=ProbeGroupWithTargetsResponse)
def get_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@app.post("/api/groups", response_model=ProbeGroupResponse)
def create_group(group: ProbeGroupCreate, db: Session = Depends(get_db)):
    db_group = ProbeGroup(**group.model_dump())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group


@app.put("/api/groups/{group_id}", response_model=ProbeGroupResponse)
def update_group(group_id: int, group_update: ProbeGroupUpdate, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    update_data = group_update.model_dump(exclude_unset=True)

    threshold_fields = ["degrade_threshold", "down_threshold", "success_threshold"]
    has_threshold_change = any(field in update_data for field in threshold_fields)

    for key, value in update_data.items():
        setattr(group, key, value)

    if has_threshold_change:
        for target in group.targets:
            if "degrade_threshold" in update_data:
                target.degrade_threshold = group.degrade_threshold
            if "down_threshold" in update_data:
                target.down_threshold = group.down_threshold
            if "success_threshold" in update_data:
                target.success_threshold = group.success_threshold

    db.commit()
    db.refresh(group)
    return group


@app.delete("/api/groups/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for target in group.targets:
        target.group_id = None
        probe_engine.remove_target(target.id)
        probe_engine.add_target(target.id)

    db.delete(group)
    db.commit()
    return {"message": "Group deleted"}


@app.post("/api/groups/{group_id}/pause")
def pause_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for target in group.targets:
        if not target.paused:
            target.paused = True
            probe_engine.toggle_target(target.id, True)

    db.commit()
    return {"message": "Group paused"}


@app.post("/api/groups/{group_id}/resume")
def resume_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for target in group.targets:
        if target.paused:
            target.paused = False
            probe_engine.toggle_target(target.id, False)

    db.commit()
    return {"message": "Group resumed"}


@app.post("/api/groups/{group_id}/silence")
def silence_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for target in group.targets:
        target.silenced = True

    db.commit()
    return {"message": "Group silenced"}


@app.post("/api/groups/{group_id}/unsilence")
def unsilence_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for target in group.targets:
        target.silenced = False

    db.commit()
    return {"message": "Group unsilenced"}


@app.post("/api/groups/{group_id}/apply-thresholds")
def apply_group_thresholds(group_id: int, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for target in group.targets:
        target.degrade_threshold = group.degrade_threshold
        target.down_threshold = group.down_threshold
        target.success_threshold = group.success_threshold

    db.commit()
    return {"message": "Thresholds applied to all targets in group"}


@app.get("/api/targets", response_model=List[ProbeTargetResponse])
def list_targets(db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload
    targets = db.query(ProbeTarget).options(joinedload(ProbeTarget.group)).order_by(ProbeTarget.id.asc()).all()
    return [_enrich_target(t) for t in targets]


@app.post("/api/targets", response_model=ProbeTargetResponse)
def create_target(target: ProbeTargetCreate, db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload
    db_target = ProbeTarget(**target.model_dump())
    db.add(db_target)
    db.commit()
    db.refresh(db_target)
    probe_engine.add_target(db_target.id)
    db_target = db.query(ProbeTarget).options(joinedload(ProbeTarget.group)).filter(ProbeTarget.id == db_target.id).first()
    return _enrich_target(db_target)


@app.get("/api/targets/{target_id}", response_model=ProbeTargetResponse)
def get_target(target_id: int, db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload
    target = db.query(ProbeTarget).options(joinedload(ProbeTarget.group)).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return _enrich_target(target)


@app.put("/api/targets/{target_id}", response_model=ProbeTargetResponse)
def update_target(target_id: int, target_update: ProbeTargetUpdate, db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload
    target = db.query(ProbeTarget).options(joinedload(ProbeTarget.group)).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    old_paused = target.paused

    update_data = target_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(target, key, value)

    db.commit()
    db.refresh(target)

    if "paused" in update_data and old_paused != target.paused:
        probe_engine.toggle_target(target.id, target.paused)

    return _enrich_target(target)


@app.delete("/api/targets/{target_id}")
def delete_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    probe_engine.remove_target(target_id)
    db.delete(target)
    db.commit()
    return {"message": "Target deleted"}


@app.post("/api/targets/{target_id}/pause")
def pause_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    target.paused = True
    db.commit()
    probe_engine.toggle_target(target_id, True)
    return {"message": "Target paused"}


@app.post("/api/targets/{target_id}/resume")
def resume_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    target.paused = False
    db.commit()
    probe_engine.toggle_target(target_id, False)
    return {"message": "Target resumed"}


@app.post("/api/targets/{target_id}/silence")
def silence_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    target.silenced = True
    db.commit()
    return {"message": "Target silenced"}


@app.post("/api/targets/{target_id}/unsilence")
def unsilence_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    target.silenced = False
    db.commit()
    return {"message": "Target unsilenced"}


@app.get("/api/targets/{target_id}/results", response_model=List[ProbeResultResponse])
def get_target_results(target_id: int, limit: int = 100, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    results = db.query(ProbeResult).filter(
        ProbeResult.target_id == target_id
    ).order_by(ProbeResult.timestamp.desc()).limit(limit).all()

    return list(reversed(results))


@app.get("/api/targets/{target_id}/history")
async def get_target_history_api(target_id: int, hours: int = 24):
    return await get_target_history(target_id, hours)


@app.get("/api/alerts", response_model=List[AlertResponse])
def list_alerts(limit: int = 50, db: Session = Depends(get_db)):
    alerts = db.query(Alert).order_by(Alert.timestamp.desc()).limit(limit).all()
    result = []
    for alert in alerts:
        alert_dict = {
            "id": alert.id,
            "target_id": alert.target_id,
            "target_name": alert.target.name if alert.target else None,
            "timestamp": alert.timestamp,
            "from_status": alert.from_status,
            "to_status": alert.to_status,
            "acknowledged": alert.acknowledged,
            "acknowledged_at": alert.acknowledged_at
        }
        result.append(alert_dict)
    return result


@app.put("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, ack: AlertAcknowledge, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.acknowledged = ack.acknowledged
    if ack.acknowledged:
        alert.acknowledged_at = datetime.utcnow()
    else:
        alert.acknowledged_at = None

    db.commit()
    return {"message": "Alert updated"}


def _get_downstream_targets(db: Session, target_id: int) -> List[ProbeTarget]:
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


def _get_upstream_targets(db: Session, target_id: int) -> List[ProbeTarget]:
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


def _update_cascade_status(db: Session, upstream_target: ProbeTarget):
    if upstream_target.status == "down" or upstream_target.status == "degraded":
        downstream_targets = _get_downstream_targets(db, upstream_target.id)
        for target in downstream_targets:
            if not target.cascade_affected:
                target.cascade_affected = True
                target.cascade_source_id = upstream_target.id
                if not target.paused:
                    target.paused = True
                    probe_engine.toggle_target(target.id, True)
    else:
        downstream_targets = _get_downstream_targets(db, upstream_target.id)
        for target in downstream_targets:
            upstreams = _get_upstream_targets(db, target.id)
            has_failed_upstream = any(
                u.status in ("down", "degraded") for u in upstreams
            )
            if not has_failed_upstream and target.cascade_affected:
                target.cascade_affected = False
                target.cascade_source_id = None
                if target.paused:
                    target.paused = False
                    probe_engine.toggle_target(target.id, False)


@app.get("/api/dependencies", response_model=List[DependencyWithNamesResponse])
def list_dependencies(db: Session = Depends(get_db)):
    deps = db.query(Dependency).order_by(Dependency.id.asc()).all()
    result = []
    for dep in deps:
        result.append({
            "id": dep.id,
            "upstream_id": dep.upstream_id,
            "upstream_name": dep.upstream_target.name if dep.upstream_target else "",
            "downstream_id": dep.downstream_id,
            "downstream_name": dep.downstream_target.name if dep.downstream_target else "",
            "description": dep.description,
            "created_at": dep.created_at
        })
    return result


@app.post("/api/dependencies", response_model=DependencyResponse)
def create_dependency(dep: DependencyCreate, db: Session = Depends(get_db)):
    if dep.upstream_id == dep.downstream_id:
        raise HTTPException(status_code=400, detail="Cannot create dependency with same target")

    upstream = db.query(ProbeTarget).filter(ProbeTarget.id == dep.upstream_id).first()
    downstream = db.query(ProbeTarget).filter(ProbeTarget.id == dep.downstream_id).first()
    if not upstream or not downstream:
        raise HTTPException(status_code=404, detail="Target not found")

    existing = db.query(Dependency).filter(
        Dependency.upstream_id == dep.upstream_id,
        Dependency.downstream_id == dep.downstream_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Dependency already exists")

    db_dep = Dependency(**dep.model_dump())
    db.add(db_dep)
    db.commit()
    db.refresh(db_dep)

    _update_cascade_status(db, upstream)
    db.commit()

    manager.broadcast_dependencies()
    manager.broadcast_targets()

    return db_dep


@app.delete("/api/dependencies/{dep_id}")
def delete_dependency(dep_id: int, db: Session = Depends(get_db)):
    dep = db.query(Dependency).filter(Dependency.id == dep_id).first()
    if not dep:
        raise HTTPException(status_code=404, detail="Dependency not found")

    downstream_id = dep.downstream_id
    downstream_target = db.query(ProbeTarget).filter(
        ProbeTarget.id == downstream_id
    ).first()

    affected_target_ids = []
    if downstream_target and downstream_target.cascade_affected:
        affected = _get_downstream_targets(db, downstream_id)
        affected_target_ids = [t.id for t in affected]
        affected_target_ids.append(downstream_id)

    db.delete(dep)
    db.commit()

    for target_id in affected_target_ids:
        target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
        if target and target.cascade_affected:
            upstreams = _get_upstream_targets(db, target_id)
            has_failed_upstream = any(
                u.status in ("down", "degraded") for u in upstreams
            )
            if not has_failed_upstream:
                target.cascade_affected = False
                target.cascade_source_id = None
                if target.paused:
                    target.paused = False
                    probe_engine.add_target(target.id)

    db.commit()

    manager.broadcast_dependencies()
    manager.broadcast_targets()

    return {"message": "Dependency deleted"}


@app.get("/api/dependencies/simulate/{target_id}", response_model=CascadeSimulationResponse)
def simulate_cascade(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    downstream = _get_downstream_targets(db, target_id)
    return {
        "source_target_id": target_id,
        "affected_target_ids": [t.id for t in downstream],
        "affected_target_names": [t.name for t in downstream]
    }


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
