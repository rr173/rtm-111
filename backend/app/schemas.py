from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ProbeTargetCreate(BaseModel):
    name: str
    type: str
    address: str
    interval: int = Field(ge=5, le=300, default=30)
    timeout: int = Field(ge=1, le=60, default=5)
    expected_status: Optional[str] = None


class ProbeTargetUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    address: Optional[str] = None
    interval: Optional[int] = Field(None, ge=5, le=300)
    timeout: Optional[int] = Field(None, ge=1, le=60)
    expected_status: Optional[str] = None
    paused: Optional[bool] = None
    silenced: Optional[bool] = None


class ProbeTargetResponse(BaseModel):
    id: int
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
    created_at: datetime

    class Config:
        from_attributes = True


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
