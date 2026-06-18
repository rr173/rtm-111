from datetime import datetime, timedelta
from app.database import SessionLocal
from app.compliance_engine import compliance_engine

db = SessionLocal()

try:
    now = datetime.utcnow()
    start_time = now - timedelta(days=1)
    end_time = now

    print(f'Test period: {start_time} to {end_time}')
    
    report = compliance_engine.generate_report(
        db=db,
        start_time=start_time,
        end_time=end_time,
        report_type='custom',
        generated_by='test'
    )
    
    print(f'\nGenerated report:')
    print(f'  Title: {report.title}')
    print(f'  Probe coverage:')
    for k, v in report.probe_coverage.items():
        if k != 'uncovered_targets':
            print(f'    {k}: {v}')
    print(f'  Uncovered targets: {len(report.probe_coverage["uncovered_targets"])}')
    for t in report.probe_coverage['uncovered_targets']:
        print(f'    - {t["name"]} (status={t["status"]}, last_check={t["last_check"]})')
    
    print(f'\n  Alert response: {report.alert_response}')
    print(f'  MTTR: {report.mttr}')
    print(f'  Config changes: {report.config_changes}')
    print(f'  Top changed targets: {report.top_changed_targets}')
finally:
    db.close()
