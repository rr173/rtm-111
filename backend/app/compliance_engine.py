from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from .models import (
    ComplianceReport, AuditLog, ProbeTarget, ProbeResult, Alert,
    Incident, MaintenanceWindow
)
import statistics


class ComplianceEngine:
    def __init__(self):
        pass

    def generate_report(
        self,
        db: Session,
        start_time: datetime,
        end_time: datetime,
        report_type: str = "custom",
        generated_by: Optional[str] = None,
    ) -> ComplianceReport:
        title = self._generate_title(start_time, end_time, report_type)

        probe_coverage = self._calculate_probe_coverage(db, start_time, end_time)
        alert_response = self._calculate_alert_response(db, start_time, end_time)
        mttr = self._calculate_mttr(db, start_time, end_time)
        config_changes = self._calculate_config_changes(db, start_time, end_time)
        top_changed_targets = self._get_top_changed_targets(db, start_time, end_time)

        audit_log_count = db.query(AuditLog).filter(
            AuditLog.created_at >= start_time,
            AuditLog.created_at <= end_time
        ).count()

        summary = {
            "total_targets": probe_coverage["total_targets"],
            "total_alerts": alert_response["total_alerts"],
            "total_audit_logs": audit_log_count,
            "total_config_changes": config_changes["total_changes"],
        }

        report = ComplianceReport(
            report_type=report_type,
            period_start=start_time,
            period_end=end_time,
            title=title,
            summary=summary,
            probe_coverage=probe_coverage,
            alert_response=alert_response,
            mttr=mttr,
            config_changes=config_changes,
            top_changed_targets=top_changed_targets,
            audit_log_count=audit_log_count,
            generated_at=datetime.utcnow(),
            generated_by=generated_by,
        )

        db.add(report)
        db.commit()
        db.refresh(report)
        return report

    def _generate_title(self, start_time: datetime, end_time: datetime, report_type: str) -> str:
        if report_type == "weekly":
            return f"{start_time.strftime('%Y年第%W周')} 合规周报"
        elif report_type == "monthly":
            return f"{start_time.strftime('%Y年%m月')} 合规月报"
        else:
            return f"合规报告 ({start_time.strftime('%Y-%m-%d')} ~ {end_time.strftime('%Y-%m-%d')})"

    def _calculate_probe_coverage(self, db: Session, start_time: datetime, end_time: datetime) -> dict:
        targets = db.query(ProbeTarget).all()
        total_targets = len(targets)

        fully_covered = 0
        partially_covered = 0
        not_covered = 0
        uncovered_targets = []

        period_duration = (end_time - start_time).total_seconds()

        for target in targets:
            results_in_period = db.query(ProbeResult).filter(
                ProbeResult.target_id == target.id,
                ProbeResult.timestamp >= start_time,
                ProbeResult.timestamp <= end_time
            ).count()

            if results_in_period == 0:
                not_covered += 1
                uncovered_targets.append({
                    "id": target.id,
                    "name": target.name,
                    "type": target.type,
                    "paused": target.paused,
                })
            else:
                expected_interval = target.interval or 30
                expected_count = period_duration / expected_interval
                coverage_ratio = results_in_period / expected_count if expected_count > 0 else 0

                if coverage_ratio >= 0.9:
                    fully_covered += 1
                else:
                    partially_covered += 1

        coverage_rate = (fully_covered + partially_covered * 0.5) / total_targets * 100 if total_targets > 0 else 0

        return {
            "total_targets": total_targets,
            "fully_covered": fully_covered,
            "partially_covered": partially_covered,
            "not_covered": not_covered,
            "coverage_rate": round(coverage_rate, 2),
            "uncovered_targets": uncovered_targets,
        }

    def _calculate_alert_response(self, db: Session, start_time: datetime, end_time: datetime) -> dict:
        alerts_in_period = db.query(Alert).filter(
            Alert.timestamp >= start_time,
            Alert.timestamp <= end_time
        ).all()

        total_alerts = len(alerts_in_period)
        acknowledged_alerts = sum(1 for a in alerts_in_period if a.acknowledged)
        unacknowledged_alerts = total_alerts - acknowledged_alerts

        acknowledgment_rate = (acknowledged_alerts / total_alerts * 100) if total_alerts > 0 else 0

        response_times = []
        for alert in alerts_in_period:
            if alert.acknowledged and alert.acknowledged_at:
                response_time = (alert.acknowledged_at - alert.timestamp).total_seconds()
                if response_time > 0:
                    response_times.append(response_time)

        avg_response_seconds = statistics.mean(response_times) if response_times else None

        return {
            "total_alerts": total_alerts,
            "acknowledged_alerts": acknowledged_alerts,
            "unacknowledged_alerts": unacknowledged_alerts,
            "acknowledgment_rate": round(acknowledgment_rate, 2),
            "avg_response_seconds": round(avg_response_seconds, 2) if avg_response_seconds else None,
        }

    def _calculate_mttr(self, db: Session, start_time: datetime, end_time: datetime) -> dict:
        incidents_in_period = db.query(Incident).filter(
            Incident.first_anomaly_at >= start_time,
            Incident.first_anomaly_at <= end_time
        ).all()

        total_incidents = len(incidents_in_period)
        recovery_times = []

        for incident in incidents_in_period:
            if incident.recovered_at:
                recovery_time = (incident.recovered_at - incident.first_anomaly_at).total_seconds()
                if recovery_time > 0:
                    recovery_times.append(recovery_time)

        avg_recovery = statistics.mean(recovery_times) if recovery_times else None
        median_recovery = statistics.median(recovery_times) if recovery_times else None
        max_recovery = max(recovery_times) if recovery_times else None
        min_recovery = min(recovery_times) if recovery_times else None

        return {
            "total_incidents": total_incidents,
            "avg_recovery_seconds": round(avg_recovery, 2) if avg_recovery else None,
            "median_recovery_seconds": round(median_recovery, 2) if median_recovery else None,
            "max_recovery_seconds": round(max_recovery, 2) if max_recovery else None,
            "min_recovery_seconds": round(min_recovery, 2) if min_recovery else None,
        }

    def _calculate_config_changes(self, db: Session, start_time: datetime, end_time: datetime) -> dict:
        audit_logs_in_period = db.query(AuditLog).filter(
            AuditLog.created_at >= start_time,
            AuditLog.created_at <= end_time
        ).all()

        target_changes = sum(1 for log in audit_logs_in_period if log.operation_type.startswith("target_"))
        group_changes = sum(1 for log in audit_logs_in_period if log.operation_type.startswith("group_"))
        threshold_changes = sum(1 for log in audit_logs_in_period if "threshold" in log.operation_type)
        maintenance_changes = sum(1 for log in audit_logs_in_period if log.operation_type.startswith("maintenance_"))
        duty_changes = sum(1 for log in audit_logs_in_period if log.operation_type.startswith("duty_"))

        total_changes = len(audit_logs_in_period)

        return {
            "total_changes": total_changes,
            "target_changes": target_changes,
            "group_changes": group_changes,
            "threshold_changes": threshold_changes,
            "maintenance_changes": maintenance_changes,
            "duty_changes": duty_changes,
        }

    def _get_top_changed_targets(
        self,
        db: Session,
        start_time: datetime,
        end_time: datetime,
        limit: int = 10
    ) -> list:
        target_change_counts = {}

        audit_logs = db.query(AuditLog).filter(
            AuditLog.created_at >= start_time,
            AuditLog.created_at <= end_time,
            AuditLog.target_id.isnot(None),
            AuditLog.target_type == "target"
        ).all()

        for log in audit_logs:
            key = (log.target_id, log.target_name or f"Target #{log.target_id}")
            target_change_counts[key] = target_change_counts.get(key, 0) + 1

        sorted_targets = sorted(
            target_change_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        return [
            {"target_id": tid, "target_name": tname, "change_count": count}
            for (tid, tname), count in sorted_targets
        ]

    def get_reports(
        self,
        db: Session,
        report_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        query = db.query(ComplianceReport)

        if report_type:
            query = query.filter(ComplianceReport.report_type == report_type)
        if start_time:
            query = query.filter(ComplianceReport.period_start >= start_time)
        if end_time:
            query = query.filter(ComplianceReport.period_end <= end_time)

        total = query.count()

        items = query.order_by(ComplianceReport.generated_at.desc()) \
            .offset((page - 1) * page_size) \
            .limit(page_size) \
            .all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

    def get_report_by_id(self, db: Session, report_id: int) -> Optional[ComplianceReport]:
        return db.query(ComplianceReport).filter(ComplianceReport.id == report_id).first()

    def delete_report(self, db: Session, report_id: int) -> bool:
        report = db.query(ComplianceReport).filter(ComplianceReport.id == report_id).first()
        if report:
            db.delete(report)
            db.commit()
            return True
        return False

    def generate_weekly_report(self, db: Session, generated_by: Optional[str] = None) -> ComplianceReport:
        now = datetime.utcnow()
        start_of_week = now - timedelta(days=now.weekday() + 7)
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_week = start_of_week + timedelta(days=7) - timedelta(microseconds=1)

        return self.generate_report(
            db=db,
            start_time=start_of_week,
            end_time=end_of_week,
            report_type="weekly",
            generated_by=generated_by,
        )

    def generate_monthly_report(self, db: Session, generated_by: Optional[str] = None) -> ComplianceReport:
        now = datetime.utcnow()
        first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if first_day.month == 1:
            last_month = first_day.replace(year=first_day.year - 1, month=12)
        else:
            last_month = first_day.replace(month=first_day.month - 1)

        if last_month.month == 12:
            next_month = last_month.replace(year=last_month.year + 1, month=1)
        else:
            next_month = last_month.replace(month=last_month.month + 1)

        end_time = next_month - timedelta(microseconds=1)

        return self.generate_report(
            db=db,
            start_time=last_month,
            end_time=end_time,
            report_type="monthly",
            generated_by=generated_by,
        )


compliance_engine = ComplianceEngine()
