from app.database import SessionLocal
from app.models import ComplianceReport
import json

db = SessionLocal()

try:
    latest_report = db.query(ComplianceReport).order_by(ComplianceReport.id.desc()).first()
    if latest_report:
        print(f"Latest report ID: {latest_report.id}")
        print(f"Title: {latest_report.title}")
        print(f"Type: {latest_report.report_type}")
        print(f"Period: {latest_report.period_start} to {latest_report.period_end}")
        print(f"\nProbe coverage (raw):")
        print(json.dumps(latest_report.probe_coverage, indent=2, ensure_ascii=False))
    else:
        print("No reports found")
finally:
    db.close()
