from datetime import datetime, timedelta
from app.database import SessionLocal
from app.compliance_engine import compliance_engine
from app.models import ProbeResult, ObserverProbeResult

db = SessionLocal()

try:
    now = datetime.utcnow()
    print(f'Current time: {now}')
    print(f'Current weekday: {now.weekday()} (0=Monday)')

    start_of_week = now - timedelta(days=now.weekday() + 7)
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=7) - timedelta(microseconds=1)
    print(f'Weekly report period: {start_of_week} to {end_of_week}')

    pr_count = db.query(ProbeResult).filter(
        ProbeResult.timestamp >= start_of_week,
        ProbeResult.timestamp <= end_of_week
    ).count()
    print(f'ProbeResult in period: {pr_count}')

    opr_count = db.query(ObserverProbeResult).filter(
        ObserverProbeResult.timestamp >= start_of_week,
        ObserverProbeResult.timestamp <= end_of_week
    ).count()
    print(f'ObserverProbeResult in period: {opr_count}')

    latest = db.query(ProbeResult).order_by(ProbeResult.timestamp.desc()).first()
    if latest:
        print(f'Latest ProbeResult: {latest.timestamp}')

    report = compliance_engine.generate_weekly_report(db, generated_by='test')
    print(f'\nGenerated report:')
    print(f'  Title: {report.title}')
    print(f'  Period: {report.period_start} to {report.period_end}')
    print(f'  Probe coverage: {report.probe_coverage}')
finally:
    db.close()
