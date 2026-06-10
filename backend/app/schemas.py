from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ProbeGroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = "#3b82f6"
    degrade_threshold: Optional[int] = Field(2, ge=1, le=100)
    down_threshold: Optional[int] = Field(5, ge=1, le=100)
    success_threshold: Optional[int] = Field(3, ge=1, le=100)
    adaptive_enabled: Optional[bool] = False
    slow_interval: Optional[int] = Field(60, ge=5, le=600)
    fast_interval: Optional[int] = Field(5, ge=1, le=120)
    silent_start: Optional[str] = None
    silent_end: Optional[str] = None


class ProbeGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    degrade_threshold: Optional[int] = Field(None, ge=1, le=100)
    down_threshold: Optional[int] = Field(None, ge=1, le=100)
    success_threshold: Optional[int] = Field(None, ge=1, le=100)
    adaptive_enabled: Optional[bool] = None
    slow_interval: Optional[int] = Field(None, ge=5, le=600)
    fast_interval: Optional[int] = Field(None, ge=1, le=120)
    silent_start: Optional[str] = None
    silent_end: Optional[str] = None


class ProbeGroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    color: str
    degrade_threshold: int
    down_threshold: int
    success_threshold: int
    adaptive_enabled: bool
    slow_interval: int
    fast_interval: int
    silent_start: Optional[str] = None
    silent_end: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProbeTargetCreate(BaseModel):
    name: str
    type: str
    address: str
    group_id: Optional[int] = None
    rule_id: Optional[int] = None
    interval: int = Field(ge=5, le=300, default=30)
    timeout: int = Field(ge=1, le=60, default=5)
    expected_status: Optional[str] = None
    degrade_threshold: Optional[int] = Field(None, ge=1, le=100)
    down_threshold: Optional[int] = Field(None, ge=1, le=100)
    success_threshold: Optional[int] = Field(None, ge=1, le=100)
    adaptive_enabled: Optional[bool] = False
    slow_interval: Optional[int] = Field(60, ge=5, le=600)
    fast_interval: Optional[int] = Field(5, ge=1, le=120)
    silent_start: Optional[str] = None
    silent_end: Optional[str] = None


class ProbeTargetUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    address: Optional[str] = None
    group_id: Optional[int] = None
    rule_id: Optional[int] = None
    interval: Optional[int] = Field(None, ge=5, le=300)
    timeout: Optional[int] = Field(None, ge=1, le=60)
    expected_status: Optional[str] = None
    paused: Optional[bool] = None
    silenced: Optional[bool] = None
    degrade_threshold: Optional[int] = Field(None, ge=1, le=100)
    down_threshold: Optional[int] = Field(None, ge=1, le=100)
    success_threshold: Optional[int] = Field(None, ge=1, le=100)
    adaptive_enabled: Optional[bool] = None
    slow_interval: Optional[int] = Field(None, ge=5, le=600)
    fast_interval: Optional[int] = Field(None, ge=1, le=120)
    silent_start: Optional[str] = None
    silent_end: Optional[str] = None


class ProbeTargetResponse(BaseModel):
    id: int
    group_id: Optional[int] = None
    rule_id: Optional[int] = None
    rule_name: Optional[str] = None
    name: str
    type: str
    address: str
    interval: int
    timeout: int
    expected_status: Optional[str]
    paused: bool
    silenced: bool
    status: str
    cascade_affected: bool
    cascade_source_id: Optional[int] = None
    cascade_source_name: Optional[str] = None
    consecutive_failures: int
    consecutive_successes: int
    last_check: Optional[datetime]
    degrade_threshold: Optional[int] = None
    down_threshold: Optional[int] = None
    success_threshold: Optional[int] = None
    adaptive_enabled: bool
    slow_interval: int
    fast_interval: int
    silent_start: Optional[str] = None
    silent_end: Optional[str] = None
    current_interval: Optional[int] = None
    next_probe_at: Optional[datetime] = None
    in_silent_window: Optional[bool] = None
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


class DependencyCreate(BaseModel):
    upstream_id: int
    downstream_id: int
    description: Optional[str] = None


class DependencyUpdate(BaseModel):
    description: Optional[str] = None


class DependencyResponse(BaseModel):
    id: int
    upstream_id: int
    downstream_id: int
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DependencyWithNamesResponse(BaseModel):
    id: int
    upstream_id: int
    upstream_name: str
    downstream_id: int
    downstream_name: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CascadeSimulationRequest(BaseModel):
    target_id: int


class CascadeSimulationResponse(BaseModel):
    source_target_id: int
    affected_target_ids: List[int]
    affected_target_names: List[str]


class ProbeRuleStepCreate(BaseModel):
    step_order: int = 0
    name: str
    step_type: str
    config: Optional[Dict[str, Any]] = None
    timeout: int = Field(5, ge=1, le=120)
    pass_condition: Optional[Dict[str, Any]] = None


class ProbeRuleStepResponse(BaseModel):
    id: int
    version_id: int
    step_order: int
    name: str
    step_type: str
    config: Optional[Dict[str, Any]] = None
    timeout: int
    pass_condition: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ProbeRuleVersionCreate(BaseModel):
    execution_mode: str = "sequence"
    steps: List[ProbeRuleStepCreate]


class ProbeRuleVersionResponse(BaseModel):
    id: int
    rule_id: int
    version: int
    execution_mode: str
    created_at: datetime
    steps: List[ProbeRuleStepResponse] = []

    class Config:
        from_attributes = True


class ProbeRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    execution_mode: str = "sequence"
    steps: List[ProbeRuleStepCreate] = []


class ProbeRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    execution_mode: Optional[str] = None
    steps: Optional[List[ProbeRuleStepCreate]] = None


class ProbeRuleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    current_version_id: Optional[int] = None
    current_version: Optional[int] = None
    execution_mode: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    versions: List[ProbeRuleVersionResponse] = []
    bound_target_count: int = 0

    class Config:
        from_attributes = True


class ProbeRuleStepExecutionResponse(BaseModel):
    id: int
    rule_execution_id: int
    step_id: int
    step_name: Optional[str] = None
    step_type: Optional[str] = None
    timestamp: datetime
    success: bool
    latency_ms: Optional[float]
    error_message: Optional[str]
    raw_response: Optional[str]

    class Config:
        from_attributes = True


class ProbeRuleExecutionResponse(BaseModel):
    id: int
    target_id: int
    version_id: int
    version: Optional[int] = None
    execution_mode: Optional[str] = None
    timestamp: datetime
    success: bool
    latency_ms: Optional[float]
    error_message: Optional[str]
    failed_step_id: Optional[int] = None
    failed_step_name: Optional[str] = None
    step_executions: List[ProbeRuleStepExecutionResponse] = []

    class Config:
        from_attributes = True


class ProbeRuleStepHistoryResponse(BaseModel):
    step_id: int
    step_name: str
    step_type: str
    executions: List[ProbeRuleStepExecutionResponse] = []
