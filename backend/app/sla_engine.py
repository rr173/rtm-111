from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from .models import (
    SLAContract, SLAContractTarget, SLAViolation, SLAMonthlyPerformance,
    ProbeTarget, ProbeResult, Alert, Incident, IncidentAlert
)
from .database import SessionLocal
import threading
import time
import logging

logger = logging.getLogger(__name__)


class SLAEngine:
    def __init__(self):
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("SLA Engine started")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("SLA Engine stopped")

    def _run_loop(self):
        while self.running:
            try:
                db = SessionLocal()
                try:
                    self._check_all_contracts(db)
                    self._update_monthly_performance(db)
                    db.commit()
                except Exception as e:
                    db.rollback()
                    logger.error(f"Error in SLA check loop: {e}")
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Error in SLA engine loop: {e}")
            time.sleep(60)

    def _check_all_contracts(self, db: Session):
        now = datetime.utcnow()
        contracts = db.query(SLAContract).filter(
            SLAContract.status == "active",
            SLAContract.effective_date <= now,
            SLAContract.expiry_date >= now
        ).all()

        for contract in contracts:
            self._check_contract_violations(db, contract, now)

    def _get_worst_target_for_contract(self, db: Session, contract: SLAContract, month_start: datetime, month_end: datetime):
        target_bindings = contract.targets
        if not target_bindings:
            return None, 0, 0

        worst_target = None
        worst_outage_minutes = 0
        worst_availability = 100.0

        for binding in target_bindings:
            target_id = binding.target_id
            outage_minutes, availability = self._calculate_target_outage(
                db, target_id, month_start, month_end
            )

            if outage_minutes > worst_outage_minutes:
                worst_outage_minutes = outage_minutes
                worst_availability = availability
                worst_target = binding.target

        return worst_target, worst_outage_minutes, worst_availability

    def _calculate_target_outage(self, db: Session, target_id: int, start_time: datetime, end_time: datetime):
        results = db.query(ProbeResult).filter(
            ProbeResult.target_id == target_id,
            ProbeResult.timestamp >= start_time,
            ProbeResult.timestamp <= end_time
        ).order_by(ProbeResult.timestamp.asc()).all()

        if not results:
            return 0, 100.0

        total_minutes = (end_time - start_time).total_seconds() / 60
        outage_minutes = 0
        in_outage = False
        outage_start = None

        for result in results:
            if not result.success:
                if not in_outage:
                    in_outage = True
                    outage_start = result.timestamp
            else:
                if in_outage and outage_start:
                    outage_duration = (result.timestamp - outage_start).total_seconds() / 60
                    outage_minutes += outage_duration
                    in_outage = False
                    outage_start = None

        if in_outage and outage_start:
            outage_duration = (end_time - outage_start).total_seconds() / 60
            outage_minutes += outage_duration

        availability = 100.0 - (outage_minutes / total_minutes * 100) if total_minutes > 0 else 100.0
        availability = max(0, min(100, availability))

        return outage_minutes, availability

    def _check_contract_violations(self, db: Session, contract: SLAContract, now: datetime):
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = now

        worst_target, monthly_outage, _ = self._get_worst_target_for_contract(
            db, contract, month_start, month_end
        )

        if not worst_target:
            return

        if monthly_outage > contract.max_monthly_outage_minutes:
            existing_violation = db.query(SLAViolation).filter(
                SLAViolation.contract_id == contract.id,
                SLAViolation.target_id == worst_target.id,
                SLAViolation.violation_type == "monthly_outage",
                SLAViolation.detected_at >= month_start
            ).first()

            if not existing_violation:
                exceeded = monthly_outage - contract.max_monthly_outage_minutes
                penalty = self._calculate_penalty(contract, "monthly_outage", exceeded)

                latest_alert = db.query(Alert).filter(
                    Alert.target_id == worst_target.id,
                    Alert.timestamp >= month_start
                ).order_by(Alert.timestamp.desc()).first()

                violation = SLAViolation(
                    contract_id=contract.id,
                    target_id=worst_target.id,
                    violation_type="monthly_outage",
                    detected_at=now,
                    actual_duration_minutes=monthly_outage,
                    exceeded_minutes=exceeded,
                    alert_id=latest_alert.id if latest_alert else None,
                    estimated_penalty=penalty
                )
                db.add(violation)
                logger.info(f"Created monthly outage violation for contract {contract.id}")

        self._check_single_outage_violations(db, contract, worst_target.id, month_start, now)

    def _check_single_outage_violations(self, db: Session, contract: SLAContract, target_id: int, start_time: datetime, end_time: datetime):
        results = db.query(ProbeResult).filter(
            ProbeResult.target_id == target_id,
            ProbeResult.timestamp >= start_time,
            ProbeResult.timestamp <= end_time
        ).order_by(ProbeResult.timestamp.asc()).all()

        if not results:
            return

        in_outage = False
        outage_start = None
        outage_count = 0

        for result in results:
            if not result.success:
                if not in_outage:
                    in_outage = True
                    outage_start = result.timestamp
                    outage_count += 1
            else:
                if in_outage and outage_start:
                    outage_duration = (result.timestamp - outage_start).total_seconds() / 60
                    self._maybe_create_single_outage_violation(
                        db, contract, target_id, outage_start, outage_duration
                    )
                    in_outage = False
                    outage_start = None

        if in_outage and outage_start:
            outage_duration = (end_time - outage_start).total_seconds() / 60
            self._maybe_create_single_outage_violation(
                db, contract, target_id, outage_start, outage_duration
            )

    def _maybe_create_single_outage_violation(self, db: Session, contract: SLAContract, target_id: int, outage_start: datetime, outage_duration: float):
        if outage_duration <= contract.max_single_outage_minutes:
            return

        existing_violation = db.query(SLAViolation).filter(
            SLAViolation.contract_id == contract.id,
            SLAViolation.target_id == target_id,
            SLAViolation.violation_type == "single_outage",
            SLAViolation.detected_at >= outage_start - timedelta(minutes=1),
            SLAViolation.detected_at <= outage_start + timedelta(minutes=1)
        ).first()

        if existing_violation:
            return

        exceeded = outage_duration - contract.max_single_outage_minutes
        penalty = self._calculate_penalty(contract, "single_outage", exceeded)

        latest_alert = db.query(Alert).filter(
            Alert.target_id == target_id,
            Alert.timestamp >= outage_start - timedelta(minutes=5),
            Alert.timestamp <= outage_start + timedelta(minutes=5)
        ).order_by(Alert.timestamp.desc()).first()

        violation = SLAViolation(
            contract_id=contract.id,
            target_id=target_id,
            violation_type="single_outage",
            detected_at=outage_start,
            actual_duration_minutes=outage_duration,
            exceeded_minutes=exceeded,
            alert_id=latest_alert.id if latest_alert else None,
            estimated_penalty=penalty
        )
        db.add(violation)
        logger.info(f"Created single outage violation for contract {contract.id}, duration: {outage_duration:.1f}min")

    def _calculate_penalty(self, contract: SLAContract, violation_type: str, exceeded_minutes: float) -> float:
        base_penalty = exceeded_minutes * contract.penalty_rate
        if violation_type == "monthly_outage":
            base_penalty *= 2
        return round(base_penalty, 2)

    def _update_monthly_performance(self, db: Session):
        now = datetime.utcnow()
        current_month = now.strftime("%Y-%m")

        contracts = db.query(SLAContract).all()

        for contract in contracts:
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            month_end = now

            worst_target, outage_minutes, availability = self._get_worst_target_for_contract(
                db, contract, month_start, month_end
            )

            violations = db.query(SLAViolation).filter(
                SLAViolation.contract_id == contract.id,
                SLAViolation.detected_at >= month_start,
                SLAViolation.detected_at <= month_end
            ).all()

            single_violations = [v for v in violations if v.violation_type == "single_outage"]
            monthly_violations = [v for v in violations if v.violation_type == "monthly_outage"]
            total_penalty = sum(v.estimated_penalty for v in violations)

            status = "compliant"
            if len(violations) > 0:
                status = "violated"
            elif outage_minutes > contract.max_monthly_outage_minutes * 0.8:
                status = "at_risk"

            monthly_stat = db.query(SLAMonthlyPerformance).filter(
                SLAMonthlyPerformance.contract_id == contract.id,
                SLAMonthlyPerformance.month == current_month
            ).first()

            if not monthly_stat:
                monthly_stat = SLAMonthlyPerformance(
                    contract_id=contract.id,
                    month=current_month
                )
                db.add(monthly_stat)

            monthly_stat.availability_pct = round(availability, 4)
            monthly_stat.total_outage_minutes = round(outage_minutes, 2)
            monthly_stat.violation_count = len(violations)
            monthly_stat.single_outage_violations = len(single_violations)
            monthly_stat.monthly_outage_violations = len(monthly_violations)
            monthly_stat.total_penalty = round(total_penalty, 2)
            monthly_stat.status = status

    def get_contract_current_status(self, db: Session, contract: SLAContract):
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        worst_target, outage_minutes, availability = self._get_worst_target_for_contract(
            db, contract, month_start, now
        )

        violations = db.query(SLAViolation).filter(
            SLAViolation.contract_id == contract.id,
            SLAViolation.detected_at >= month_start
        ).all()

        outage_pct = (outage_minutes / contract.max_monthly_outage_minutes * 100) if contract.max_monthly_outage_minutes > 0 else 0

        status = "compliant"
        if len(violations) > 0:
            status = "violated"
        elif outage_pct >= 80:
            status = "at_risk"

        days_until_expiry = (contract.expiry_date - now).days
        is_renewal_needed = days_until_expiry <= 30 and contract.status == "active"

        return {
            "current_month_status": status,
            "current_month_availability": round(availability, 4),
            "current_month_outage_minutes": round(outage_minutes, 2),
            "current_month_outage_pct": round(outage_pct, 2),
            "current_month_violation_count": len(violations),
            "days_until_expiry": max(0, days_until_expiry),
            "is_renewal_needed": is_renewal_needed,
        }


sla_engine = SLAEngine()
