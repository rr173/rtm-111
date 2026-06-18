from datetime import datetime, timedelta
from app.database import SessionLocal
from app.models import ProbeTarget, ProbeResult, ObserverProbeResult
from app.compliance_engine import compliance_engine

db = SessionLocal()

try:
    targets = db.query(ProbeTarget).all()
    print(f"Total targets: {len(targets)}")
    for t in targets:
        print(f"  - {t.name}: paused={t.paused}, last_check={t.last_check}")
    
    print("\n--- Checking probe results ---")
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=2)
    print(f"Time range: {start_time} to {end_time}")
    
    for t in targets:
        if t.paused:
            continue
        pr_count = db.query(ProbeResult).filter(
            ProbeResult.target_id == t.id,
            ProbeResult.timestamp >= start_time,
            ProbeResult.timestamp <= end_time
        ).count()
        opr_count = db.query(ObserverProbeResult).filter(
            ObserverProbeResult.target_id == t.id,
            ObserverProbeResult.timestamp >= start_time,
            ObserverProbeResult.timestamp <= end_time
        ).count()
        print(f"  {t.name}: ProbeResult={pr_count}, ObserverProbeResult={opr_count}, total={pr_count + opr_count}")
    
    print("\n--- Testing coverage calculation ---")
    coverage = compliance_engine._calculate_probe_coverage(db, start_time, end_time)
    print(f"Result: {coverage}")
    
finally:
    db.close()
