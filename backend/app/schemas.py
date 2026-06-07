from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ProbeGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = "#3b82f6"
    degrade_threshold: Optional[int] = Field(2, ge=1, le=100)
    down_threshold: Optional[int] = Field(5, ge=1, le=100)
    success_threshold: Optional[int] = Field(3, ge=1, le=100)


class ProbeGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    degrade_threshold: Optional[int] = Field(None, ge=1, le=100)
    down_threshold: Optional[int] = Field(None, ge=1, le=100)
    success_threshold: Optional[int] = Field(None, ge=1, le=100)


class ProbeGroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    color: str
    degrade_threshold: int
    down_threshold: int
    success_threshold: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProbeTargetCreate(BaseModel):
    name: str
    type: str
    address: str
    group_id: Optional[int] = None
    interval: int = Field(ge=5, le=300, default=30)
    timeout: int = Field(ge=1, le=60, default=5)
    expected_status: Optional[str] = None
    degrade_threshold: Optional[int] = Field(None, ge=1, le=100)
    down_threshold: Optional[int] = Field(None, ge=1, le=100)
    success_threshold: Optional[int] = Field(None, ge=1, le=100)


class ProbeTargetUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    address: Optional[str] = None
    group_id: Optional[int] = None
    interval: Optional[int] = Field(None, ge=5, le=300)
    timeout: Optional[int] = Field(None, ge=1, le=60)
    expected_status: Optional[str] = None
    paused: Optional[bool] = None
    silenced: Optional[bool] = None
    degrade_threshold: Optional[int] = Field(None, ge=1, le=100)
    down_threshold: Optional[int] = Field(None, ge=1, le=100)
    success_threshold: Optional[int] = Field(None, ge=1, le=100)


class ProbeTargetResponse(BaseModel):
    id: int
    group_id: Optional[int] = None
    name: str
    type: str
    address: str
    interval: int
    timeout: int
    expected_status: Optional[str]
    paused: bool
    silenced: bool
    status: str
    consecutive_failures: int
    consecutive_successes: int
    last_check: Optional[datetime]
    degrade_threshold: Optional[int] = None
    down_threshold: Optional[int] = None
    success_threshold: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProbeGroupWithTargetsResponse(ProbeGroupResponse):
    targets: List[ProbeTargetResponse] = []


class ProbeResultResponse(BaseModel):
    id: int
    target_id: int
    timestamp: datetime
    success: bool
    latency_ms: Optional[float]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: int
    target_id: int
    target_name: Optional[str] = None
    timestamp: datetime
    from_status: str
    to_status: str
    acknowledged: bool
    acknowledged_at: Optional[datetime]

    class Config:
        from_attributes = True


class AlertAcknowledge(BaseModel):
    acknowledged: bool
