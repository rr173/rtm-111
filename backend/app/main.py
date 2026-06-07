from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from .database import engine, get_db, Base
from .models import ProbeTarget, ProbeResult, Alert
from .schemas import (
    ProbeTargetCreate, ProbeTargetUpdate, ProbeTargetResponse,
    ProbeResultResponse, AlertResponse, AlertAcknowledge
)
from .probe_engine import probe_engine
from .websocket_manager import manager, get_target_history

Base.metadata.create_all(bind=engine)

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
        count = db.query(ProbeTarget).count()
        if count > 0:
            return

        now = datetime.utcnow()

        target1 = ProbeTarget(
            name="示例服务-健康",
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

        db.commit()
    except Exception as e:
        print(f"Demo data init error: {e}")
        db.rollback()
    finally:
        db.close()


@app.get("/api/targets", response_model=List[ProbeTargetResponse])
def list_targets(db: Session = Depends(get_db)):
    targets = db.query(ProbeTarget).order_by(ProbeTarget.id.asc()).all()
    return targets


@app.post("/api/targets", response_model=ProbeTargetResponse)
def create_target(target: ProbeTargetCreate, db: Session = Depends(get_db)):
    db_target = ProbeTarget(**target.model_dump())
    db.add(db_target)
    db.commit()
    db.refresh(db_target)
    probe_engine.add_target(db_target.id)
    return db_target


@app.get("/api/targets/{target_id}", response_model=ProbeTargetResponse)
def get_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return target


@app.put("/api/targets/{target_id}", response_model=ProbeTargetResponse)
def update_target(target_id: int, target_update: ProbeTargetUpdate, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
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

    return target


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


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
