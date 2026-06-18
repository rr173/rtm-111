from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any
from .models import AuditLog, ProbeTarget, ProbeGroup, Alert, MaintenanceWindow, DutySwap
import json


OPERATION_TYPES = {
    "target_create": "目标创建",
    "target_update": "目标更新",
    "target_delete": "目标删除",
    "target_pause": "目标暂停",
    "target_resume": "目标恢复",
    "target_silence": "目标消声",
    "target_unsilence": "目标取消消声",
    "target_threshold_update": "阈值调整",
    "group_create": "分组创建",
    "group_update": "分组更新",
    "group_delete": "分组删除",
    "group_pause": "分组暂停",
    "group_resume": "分组恢复",
    "group_silence": "分组消声",
    "group_unsilence": "分组取消消声",
    "group_threshold_apply": "分组阈值应用",
    "alert_acknowledge": "告警确认",
    "maintenance_create": "维护窗口创建",
    "maintenance_update": "维护窗口更新",
    "maintenance_delete": "维护窗口删除",
    "maintenance_extend": "维护窗口延期",
    "maintenance_cancel": "维护窗口取消",
    "duty_swap_create": "值班换班",
    "duty_schedule_update": "值班调度更新",
    "incident_acknowledge": "事件确认",
    "incident_transfer": "事件转派",
    "incident_resolve": "事件解决",
}


class AuditEngine:
    def __init__(self):
        pass

    def _serialize_value(self, value: Any) -> Optional[Dict[str, Any]]:
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        if hasattr(value, '__dict__'):
            result = {}
            for key, val in value.__dict__.items():
                if key.startswith('_'):
                    continue
                if isinstance(val, datetime):
                    result[key] = val.isoformat()
                else:
                    try:
                        json.dumps(val)
                        result[key] = val
                    except (TypeError, ValueError):
                        result[key] = str(val)
            return result
        return {"value": str(value)}

    def log_operation(
        self,
        db: Session,
        operator: Optional[str],
        operation_type: str,
        target_type: str,
        target_id: Optional[int] = None,
        target_name: Optional[str] = None,
        old_value: Any = None,
        new_value: Any = None,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            operator=operator,
            operation_type=operation_type,
            target_type=target_type,
            target_id=target_id,
            target_name=target_name,
            old_value=self._serialize_value(old_value),
            new_value=self._serialize_value(new_value),
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.utcnow(),
        )
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
        return audit_log

    def get_audit_logs(
        self,
        db: Session,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        operation_type: Optional[str] = None,
        operator: Optional[str] = None,
        target_name: Optional[str] = None,
        target_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        query = db.query(AuditLog)

        if start_time:
            query = query.filter(AuditLog.created_at >= start_time)
        if end_time:
            query = query.filter(AuditLog.created_at <= end_time)
        if operation_type:
            query = query.filter(AuditLog.operation_type == operation_type)
        if operator:
            query = query.filter(AuditLog.operator.like(f"%{operator}%"))
        if target_name:
            query = query.filter(AuditLog.target_name.like(f"%{target_name}%"))
        if target_type:
            query = query.filter(AuditLog.target_type == target_type)

        total = query.count()
        total_pages = (total + page_size - 1) // page_size

        items = query.order_by(AuditLog.created_at.desc()) \
            .offset((page - 1) * page_size) \
            .limit(page_size) \
            .all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def get_operation_types(self) -> Dict[str, str]:
        return OPERATION_TYPES

    def get_distinct_operators(self, db: Session) -> list:
        result = db.query(AuditLog.operator).distinct().all()
        return [r[0] for r in result if r[0]]


audit_engine = AuditEngine()
