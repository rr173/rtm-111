import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from .database import SessionLocal
from .models import (
    ProbeTarget, ProbeResult, Alert, ProbeGroup,
    HealthScore, HealthScoreHistory, HealthRankingSnapshot,
    CapacityConfig
)


class HealthEngine:
    def __init__(self):
        self.running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._task: Optional[asyncio.Task] = None
        self._update_callbacks: List[Callable] = []
        self._check_interval = 3600
        self._weights = {
            'availability': 0.4,
            'latency': 0.2,
            'alert': 0.2,
            'stability': 0.2
        }

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def register_update_callback(self, callback: Callable):
        self._update_callbacks.append(callback)

    async def start(self):
        self.running = True
        self._loop = asyncio.get_running_loop()
        self._task = asyncio.create_task(self._run_scheduler())
        print("Health engine started")
        asyncio.create_task(self._initial_calculate())

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("Health engine stopped")

    async def _initial_calculate(self):
        await asyncio.sleep(5)
        try:
            self.calculate_all_scores()
        except Exception as e:
            print(f"Initial health calculation error: {e}")

    async def _run_scheduler(self):
        while self.running:
            try:
                now = datetime.utcnow()
                next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
                wait_seconds = (next_hour - now).total_seconds()
                await asyncio.sleep(wait_seconds)

                if self.running:
                    self.calculate_all_scores()
            except Exception as e:
                print(f"Health scheduler error: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(60)

    def _get_availability_7d(self, db: Session, target_id: int) -> float:
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        results = db.query(ProbeResult).filter(
            and_(
                ProbeResult.target_id == target_id,
                ProbeResult.timestamp >= seven_days_ago
            )
        ).all()

        if not results:
            return 100.0

        success_count = sum(1 for r in results if r.success)
        total_count = len(results)
        return (success_count / total_count) * 100.0

    def _get_avg_latency(self, db: Session, target_id: int) -> Optional[float]:
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        results = db.query(ProbeResult).filter(
            and_(
                ProbeResult.target_id == target_id,
                ProbeResult.timestamp >= seven_days_ago,
                ProbeResult.success == True,
                ProbeResult.latency_ms.isnot(None)
            )
        ).all()

        if not results:
            return None

        latencies = [r.latency_ms for r in results if r.latency_ms is not None]
        return sum(latencies) / len(latencies)

    def _get_latency_threshold(self, db: Session, target: ProbeTarget) -> float:
        capacity_config = db.query(CapacityConfig).filter(
            CapacityConfig.target_id == target.id
        ).first()

        if capacity_config and capacity_config.max_latency_ms:
            return capacity_config.max_latency_ms

        group_config = db.query(CapacityConfig).filter(
            CapacityConfig.group_id == target.group_id
        ).first()

        if group_config and group_config.max_latency_ms:
            return group_config.max_latency_ms

        return 500.0

    def _get_alert_count_7d(self, db: Session, target_id: int) -> int:
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        count = db.query(Alert).filter(
            and_(
                Alert.target_id == target_id,
                Alert.timestamp >= seven_days_ago
            )
        ).count()
        return count

    def _get_consecutive_healthy_hours(self, db: Session, target_id: int) -> int:
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        results = db.query(ProbeResult).filter(
            and_(
                ProbeResult.target_id == target_id,
                ProbeResult.timestamp >= seven_days_ago
            )
        ).order_by(desc(ProbeResult.timestamp)).all()

        if not results:
            return 0

        consecutive_hours = 0
        hourly_status = {}

        for result in results:
            hour = result.timestamp.replace(minute=0, second=0, microsecond=0)
            if hour not in hourly_status:
                hourly_status[hour] = {'success': 0, 'total': 0}
            hourly_status[hour]['total'] += 1
            if result.success:
                hourly_status[hour]['success'] += 1

        sorted_hours = sorted(hourly_status.keys(), reverse=True)

        for hour in sorted_hours:
            status = hourly_status[hour]
            if status['total'] > 0 and (status['success'] / status['total']) >= 0.95:
                consecutive_hours += 1
            else:
                break

        return consecutive_hours

    def _calculate_availability_score(self, availability_pct: float) -> float:
        if availability_pct >= 99.9:
            return 100.0
        elif availability_pct >= 99.5:
            return 90.0 + (availability_pct - 99.5) * 20
        elif availability_pct >= 99.0:
            return 80.0 + (availability_pct - 99.0) * 20
        elif availability_pct >= 95.0:
            return 50.0 + (availability_pct - 95.0) * 7.5
        elif availability_pct >= 90.0:
            return 30.0 + (availability_pct - 90.0) * 4
        else:
            return max(0.0, availability_pct * 0.3)

    def _calculate_latency_score(self, avg_latency: float, threshold: float) -> float:
        if avg_latency is None:
            return 100.0

        ratio = avg_latency / threshold

        if ratio <= 0.3:
            return 100.0
        elif ratio <= 0.5:
            return 90.0 + (0.5 - ratio) * 50
        elif ratio <= 0.7:
            return 70.0 + (0.7 - ratio) * 100
        elif ratio <= 1.0:
            return 40.0 + (1.0 - ratio) * 100
        else:
            return max(0.0, 40.0 - (ratio - 1.0) * 40)

    def _calculate_alert_score(self, alert_count: int) -> float:
        if alert_count == 0:
            return 100.0
        elif alert_count == 1:
            return 85.0
        elif alert_count == 2:
            return 70.0
        elif alert_count <= 5:
            return 50.0 + (5 - alert_count) * 6.67
        elif alert_count <= 10:
            return 25.0 + (10 - alert_count) * 5
        elif alert_count <= 20:
            return 10.0 + (20 - alert_count) * 1.5
        else:
            return max(0.0, 10.0 - (alert_count - 20) * 0.5)

    def _calculate_stability_score(self, consecutive_hours: int) -> float:
        if consecutive_hours >= 168:
            return 100.0
        elif consecutive_hours >= 72:
            return 80.0 + (consecutive_hours - 72) * (20 / 96)
        elif consecutive_hours >= 24:
            return 60.0 + (consecutive_hours - 24) * (20 / 48)
        elif consecutive_hours >= 12:
            return 40.0 + (consecutive_hours - 12) * (20 / 12)
        elif consecutive_hours >= 6:
            return 20.0 + (consecutive_hours - 6) * (20 / 6)
        elif consecutive_hours >= 1:
            return 5.0 + (consecutive_hours - 1) * 3
        else:
            return 0.0

    def calculate_target_score(self, db: Session, target: ProbeTarget) -> Optional[HealthScore]:
        if target.paused:
            return None

        availability_7d = self._get_availability_7d(db, target.id)
        avg_latency = self._get_avg_latency(db, target.id)
        latency_threshold = self._get_latency_threshold(db, target)
        alert_count_7d = self._get_alert_count_7d(db, target.id)
        consecutive_healthy_hours = self._get_consecutive_healthy_hours(db, target.id)

        availability_score = self._calculate_availability_score(availability_7d)
        latency_score = self._calculate_latency_score(avg_latency, latency_threshold)
        alert_score = self._calculate_alert_score(alert_count_7d)
        stability_score = self._calculate_stability_score(consecutive_healthy_hours)

        overall_score = (
            availability_score * self._weights['availability'] +
            latency_score * self._weights['latency'] +
            alert_score * self._weights['alert'] +
            stability_score * self._weights['stability']
        )

        existing = db.query(HealthScore).filter(HealthScore.target_id == target.id).first()

        group_name = target.group.name if target.group else None

        if existing:
            previous_score = existing.overall_score
            if overall_score > previous_score + 0.5:
                score_trend = "up"
            elif overall_score < previous_score - 0.5:
                score_trend = "down"
            else:
                score_trend = "flat"

            existing.previous_score = previous_score
            existing.overall_score = round(overall_score, 1)
            existing.availability_score = round(availability_score, 1)
            existing.latency_score = round(latency_score, 1)
            existing.alert_score = round(alert_score, 1)
            existing.stability_score = round(stability_score, 1)
            existing.availability_7d = round(availability_7d, 2)
            existing.avg_latency_ms = round(avg_latency, 1) if avg_latency else None
            existing.latency_threshold_ms = latency_threshold
            existing.alert_count_7d = alert_count_7d
            existing.consecutive_healthy_hours = consecutive_healthy_hours
            existing.score_trend = score_trend
            existing.last_calculated_at = datetime.utcnow()
            existing.group_name = group_name

            return existing
        else:
            health_score = HealthScore(
                target_id=target.id,
                target_name=target.name,
                group_id=target.group_id,
                group_name=group_name,
                overall_score=round(overall_score, 1),
                availability_score=round(availability_score, 1),
                latency_score=round(latency_score, 1),
                alert_score=round(alert_score, 1),
                stability_score=round(stability_score, 1),
                availability_weight=self._weights['availability'],
                latency_weight=self._weights['latency'],
                alert_weight=self._weights['alert'],
                stability_weight=self._weights['stability'],
                availability_7d=round(availability_7d, 2),
                avg_latency_ms=round(avg_latency, 1) if avg_latency else None,
                latency_threshold_ms=latency_threshold,
                alert_count_7d=alert_count_7d,
                consecutive_healthy_hours=consecutive_healthy_hours,
                previous_score=None,
                score_trend="flat",
                last_calculated_at=datetime.utcnow()
            )
            db.add(health_score)
            return health_score

    def calculate_all_scores(self):
        db = SessionLocal()
        try:
            targets = db.query(ProbeTarget).filter(
                ProbeTarget.paused == False,
                ProbeTarget.deprecated == False
            ).all()

            scores = []
            for target in targets:
                try:
                    score = self.calculate_target_score(db, target)
                    if score:
                        scores.append(score)
                except Exception as e:
                    print(f"Error calculating score for target {target.id}: {e}")

            db.flush()

            snapshot_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

            for score in scores:
                history = HealthScoreHistory(
                    target_id=score.target_id,
                    target_name=score.target_name,
                    group_id=score.group_id,
                    group_name=score.group_name,
                    overall_score=score.overall_score,
                    availability_score=score.availability_score,
                    latency_score=score.latency_score,
                    alert_score=score.alert_score,
                    stability_score=score.stability_score,
                    availability_7d=score.availability_7d,
                    avg_latency_ms=score.avg_latency_ms,
                    alert_count_7d=score.alert_count_7d,
                    consecutive_healthy_hours=score.consecutive_healthy_hours,
                    snapshot_hour=snapshot_hour
                )
                db.add(history)

            db.commit()

            self._save_ranking_snapshot(db, scores, snapshot_hour)
            self._broadcast_update()

            print(f"Health scores calculated for {len(scores)} targets at {snapshot_hour}")
            return scores
        except Exception as e:
            db.rollback()
            print(f"Calculate all scores error: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            db.close()

    def _save_ranking_snapshot(self, db: Session, scores: List[HealthScore], snapshot_time: datetime):
        sorted_scores = sorted(scores, key=lambda s: s.overall_score)

        snapshot_data = []
        for rank, score in enumerate(sorted_scores, 1):
            snapshot_data.append({
                'rank': rank,
                'target_id': score.target_id,
                'target_name': score.target_name,
                'group_id': score.group_id,
                'group_name': score.group_name,
                'overall_score': score.overall_score,
                'availability_score': score.availability_score,
                'latency_score': score.latency_score,
                'alert_score': score.alert_score,
                'stability_score': score.stability_score,
            })

        avg_score = sum(s.overall_score for s in scores) / len(scores) if scores else 0

        snapshot = HealthRankingSnapshot(
            snapshot_time=snapshot_time,
            total_targets=len(scores),
            avg_score=round(avg_score, 1),
            data=snapshot_data
        )
        db.add(snapshot)

    def _broadcast_update(self):
        for callback in self._update_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Health update callback error: {e}")

    def get_health_scores(self, group_id: Optional[int] = None, min_score: Optional[float] = None,
                         sort_order: str = 'asc', limit: Optional[int] = None) -> List[HealthScore]:
        db = SessionLocal()
        try:
            query = db.query(HealthScore)

            if group_id is not None:
                query = query.filter(HealthScore.group_id == group_id)

            if min_score is not None:
                query = query.filter(HealthScore.overall_score < min_score)

            if sort_order == 'asc':
                query = query.order_by(HealthScore.overall_score.asc())
            else:
                query = query.order_by(HealthScore.overall_score.desc())

            if limit:
                query = query.limit(limit)

            return query.all()
        finally:
            db.close()

    def get_target_health_history(self, target_id: int, days: int = 7) -> List[HealthScoreHistory]:
        db = SessionLocal()
        try:
            start_time = datetime.utcnow() - timedelta(days=days)
            history = db.query(HealthScoreHistory).filter(
                and_(
                    HealthScoreHistory.target_id == target_id,
                    HealthScoreHistory.snapshot_hour >= start_time
                )
            ).order_by(HealthScoreHistory.snapshot_hour.asc()).all()
            return history
        finally:
            db.close()

    def get_ranking_snapshots(self, date: Optional[str] = None, days: int = 7) -> List[HealthRankingSnapshot]:
        db = SessionLocal()
        try:
            query = db.query(HealthRankingSnapshot)

            if date:
                try:
                    target_date = datetime.strptime(date, '%Y-%m-%d')
                    next_day = target_date + timedelta(days=1)
                    query = query.filter(
                        and_(
                            HealthRankingSnapshot.snapshot_time >= target_date,
                            HealthRankingSnapshot.snapshot_time < next_day
                        )
                    )
                except ValueError:
                    pass
            else:
                start_time = datetime.utcnow() - timedelta(days=days)
                query = query.filter(HealthRankingSnapshot.snapshot_time >= start_time)

            return query.order_by(desc(HealthRankingSnapshot.snapshot_time)).all()
        finally:
            db.close()

    def get_score_level(self, score: float) -> str:
        if score >= 90:
            return 'excellent'
        elif score >= 70:
            return 'good'
        else:
            return 'poor'


health_engine = HealthEngine()
