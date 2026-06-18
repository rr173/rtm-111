from pydantic import BaseModel, Field, field_validator, model_validator
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
    source_id: Optional[int] = None
    source_name: Optional[str] = None
    deprecated: bool
    deprecated_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
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


class SnapshotCreate(BaseModel):
    name: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime


class SnapshotUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class SnapshotDataPoint(BaseModel):
    target_id: int
    target_name: str
    timestamp: datetime
    status: str
    latency_ms: Optional[float]
    success: bool
    consecutive_failures: int
    consecutive_successes: int
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class SnapshotAlertPoint(BaseModel):
    target_id: int
    target_name: str
    timestamp: datetime
    from_status: str
    to_status: str

    class Config:
        from_attributes = True


class SnapshotResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    target_count: int
    data_point_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class SnapshotDetailResponse(SnapshotResponse):
    data: List[SnapshotDataPoint] = []
    alerts: List[SnapshotAlertPoint] = []


class SnapshotTimelinePoint(BaseModel):
    timestamp: datetime
    targets: Dict[str, Any]


class SnapshotComparisonResponse(BaseModel):
    snapshot_a: SnapshotResponse
    snapshot_b: SnapshotResponse
    common_targets: List[str]
    comparisons: List[Dict[str, Any]]


class ObservationPointCreate(BaseModel):
    name: str
    region: str
    description: Optional[str] = None
    status: Optional[str] = "online"


class ObservationPointUpdate(BaseModel):
    name: Optional[str] = None
    region: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ObservationPointResponse(BaseModel):
    id: int
    name: str
    region: str
    status: str
    last_heartbeat: Optional[datetime] = None
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TargetObserverBindingCreate(BaseModel):
    target_id: int
    observer_ids: List[int]


class ObserverResultResponse(BaseModel):
    id: int
    target_id: int
    observer_id: int
    observer_name: Optional[str] = None
    observer_region: Optional[str] = None
    round_id: str
    timestamp: datetime
    success: bool
    latency_ms: Optional[float] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class ObserverRoundSummary(BaseModel):
    round_id: str
    target_id: int
    timestamp: datetime
    unified_status: str
    total_observers: int
    online_observers: int
    success_count: int
    failure_count: int
    offline_count: int
    results: List[ObserverResultResponse] = []


class ObservationMatrixCell(BaseModel):
    target_id: int
    target_name: str
    observer_id: int
    observer_name: str
    observer_region: str
    observer_status: str
    latest_status: Optional[str] = None
    latest_latency: Optional[float] = None
    latest_timestamp: Optional[datetime] = None


class ChangeTargetCreate(BaseModel):
    target_id: int


class ChangeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    planned_time: datetime
    target_ids: List[int] = []
    notes: Optional[str] = None
    created_by: Optional[str] = None


class ChangeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    planned_time: Optional[datetime] = None
    target_ids: Optional[List[int]] = None
    notes: Optional[str] = None


class ChangeTargetResponse(BaseModel):
    id: int
    target_id: int
    target_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChangeEventResponse(BaseModel):
    id: int
    event_type: str
    message: str
    timestamp: datetime
    data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class ChangeResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    planned_time: datetime
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    baseline_snapshot_id: Optional[int] = None
    result_snapshot_id: Optional[int] = None
    conclusion: Optional[str] = None
    conclusion_reason: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    targets: List[ChangeTargetResponse] = []
    events: List[ChangeEventResponse] = []
    target_count: int = 0

    class Config:
        from_attributes = True


class TargetActiveChange(BaseModel):
    change_id: int
    change_name: str
    change_status: str
    start_time: Optional[datetime] = None


class ChangeStatusDiff(BaseModel):
    target_id: int
    target_name: str
    baseline_status: str
    current_status: str
    status_changed: bool


class ChangeAlertStats(BaseModel):
    baseline_count: int
    current_count: int
    new_alerts: int
    resolved_alerts: int
    target_alerts: Dict[str, int]


class ChangeRegionDivergence(BaseModel):
    target_id: int
    target_name: str
    regions: Dict[str, Dict[str, Any]]
    has_divergence: bool
    divergent_regions: List[str]


class ChangeObservationResponse(BaseModel):
    change: ChangeResponse
    target_ids: List[int]
    target_names: List[str]
    downstream_target_ids: List[int]
    downstream_target_names: List[str]
    all_target_ids: List[int]
    status_diff: List[ChangeStatusDiff]
    alert_stats: ChangeAlertStats
    region_divergence: List[ChangeRegionDivergence]
    baseline_metrics: Dict[str, Any]
    current_metrics: Dict[str, Any]
    alerts_timeline: List[Dict[str, Any]]
    comparison_result: Optional[Dict[str, Any]] = None


class ChangeComparisonResponse(BaseModel):
    baseline_snapshot: Optional[SnapshotResponse] = None
    result_snapshot: Optional[SnapshotResponse] = None
    target_comparisons: List[Dict[str, Any]]
    overall_summary: Dict[str, Any]
    conclusion: Optional[str] = None
    conclusion_reason: Optional[str] = None


class SLOTargetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    target_id: Optional[int] = None
    group_id: Optional[int] = None
    slo_type: str = "availability"
    slo_target: float = Field(99.9, ge=0, le=100)
    latency_threshold_ms: Optional[float] = None
    window_days: int = Field(30, ge=1, le=365)


class SLOTargetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_id: Optional[int] = None
    group_id: Optional[int] = None
    slo_type: Optional[str] = None
    slo_target: Optional[float] = Field(None, ge=0, le=100)
    latency_threshold_ms: Optional[float] = None
    window_days: Optional[int] = Field(None, ge=1, le=365)


class SLOTargetResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    slo_type: str
    slo_target: float
    latency_threshold_ms: Optional[float] = None
    window_days: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SLOBudgetAttribution(BaseModel):
    service_fault: float = 0
    regional_anomaly: float = 0
    dependency_cascade: float = 0
    change_induced: float = 0


class SLOBudgetPoint(BaseModel):
    timestamp: datetime
    total_budget: float
    budget_consumed: float
    budget_remaining: float
    current_value: float
    attribution: SLOBudgetAttribution


class SLOBudgetResponse(BaseModel):
    slo_id: int
    slo_name: str
    slo_type: str
    slo_target: float
    window_days: int
    current_value: float
    total_budget: float
    budget_consumed: float
    budget_remaining: float
    budget_remaining_pct: float
    burn_rate: float
    status: str
    attribution: SLOBudgetAttribution
    timeline: List[SLOBudgetPoint] = []


class SLOBudgetOverviewItem(BaseModel):
    slo_id: int
    slo_name: str
    slo_type: str
    slo_target: float
    current_value: float
    budget_remaining_pct: float
    burn_rate: float
    status: str
    target_name: Optional[str] = None
    group_name: Optional[str] = None


class SLOPredictionResponse(BaseModel):
    slo_id: int
    slo_name: str
    current_value: float
    burn_rate: float
    hours_to_breach: Optional[float] = None
    predicted_breach_time: Optional[datetime] = None
    projected_value_24h: float
    will_breach_24h: bool


class IncidentTargetInfo(BaseModel):
    target_id: int
    target_name: str
    target_status: Optional[str] = None
    group_name: Optional[str] = None
    role: str
    first_alert_at: Optional[datetime] = None
    last_alert_at: Optional[datetime] = None
    max_severity: str

    class Config:
        from_attributes = True


class IncidentAlertInfo(BaseModel):
    alert_id: int
    target_id: int
    target_name: Optional[str] = None
    timestamp: datetime
    from_status: str
    to_status: str

    class Config:
        from_attributes = True


class IncidentTimelineEvent(BaseModel):
    id: int
    timestamp: datetime
    event_type: str
    title: str
    description: Optional[str] = None
    severity: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class IncidentNoteInfo(BaseModel):
    id: int
    author: str
    content: str
    action_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class IncidentDependencyInfo(BaseModel):
    target_id: int
    target_name: str
    status: str
    direction: str
    depth: int


class IncidentRegionDivergence(BaseModel):
    target_id: int
    target_name: str
    regions: Dict[str, Dict[str, Any]]
    has_divergence: bool
    divergent_regions: List[str]


class IncidentSLOBudgetRisk(BaseModel):
    slo_id: int
    slo_name: str
    budget_remaining_pct: float
    burn_rate: float
    status: str
    hours_to_breach: Optional[float] = None


class IncidentResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    severity: str
    status: str
    first_anomaly_at: datetime
    last_anomaly_at: datetime
    recovered_at: Optional[datetime] = None
    bleed_over_until: Optional[datetime] = None
    mitigated: bool
    mitigated_at: Optional[datetime] = None
    owner: Optional[str] = None
    acknowledged: bool
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    needs_review: bool
    review_notes: Optional[str] = None
    parent_incident_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    targets: List[IncidentTargetInfo] = []
    alerts: List[IncidentAlertInfo] = []
    timeline: List[IncidentTimelineEvent] = []
    notes: List[IncidentNoteInfo] = []
    target_count: int = 0
    alert_count: int = 0
    duration_seconds: Optional[int] = None
    upstream_dependencies: List[IncidentDependencyInfo] = []
    downstream_dependencies: List[IncidentDependencyInfo] = []
    active_changes: List[Dict[str, Any]] = []
    region_divergence: List[IncidentRegionDivergence] = []
    slo_budget_risks: List[IncidentSLOBudgetRisk] = []

    class Config:
        from_attributes = True


VALID_INCIDENT_STATUSES = {"active", "recovering", "resolved"}
VALID_INCIDENT_SEVERITIES = {"warning", "critical", "info"}
VALID_NOTE_ACTION_TYPES = {"note", "investigation", "mitigation", "observation", "transfer"}


def _validate_non_empty_str(v: Optional[str], min_len: int = 1, max_len: int = 100) -> Optional[str]:
    if v is None:
        return v
    stripped = v.strip()
    if len(stripped) < min_len:
        raise ValueError(f"must be at least {min_len} non-whitespace character(s)")
    if len(stripped) > max_len:
        raise ValueError(f"must be at most {max_len} characters")
    return stripped


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    mitigated: Optional[bool] = None
    owner: Optional[str] = None
    needs_review: Optional[bool] = None
    review_notes: Optional[str] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        if v is None:
            return v
        stripped = v.strip()
        if len(stripped) < 2:
            raise ValueError("title must be at least 2 non-whitespace characters")
        if len(stripped) > 512:
            raise ValueError("title must be at most 512 characters")
        return stripped

    @field_validator("description")
    @classmethod
    def validate_description(cls, v):
        if v is None:
            return v
        stripped = v.strip()
        if len(stripped) > 5000:
            raise ValueError("description must be at most 5000 characters")
        return stripped or None

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v):
        if v is None:
            return v
        if v not in VALID_INCIDENT_SEVERITIES:
            raise ValueError(f"severity must be one of {sorted(VALID_INCIDENT_SEVERITIES)}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is None:
            return v
        if v not in VALID_INCIDENT_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_INCIDENT_STATUSES)}")
        return v

    @field_validator("owner")
    @classmethod
    def validate_owner(cls, v):
        return _validate_non_empty_str(v, min_len=1, max_len=100)

    @field_validator("review_notes")
    @classmethod
    def validate_review_notes(cls, v):
        if v is None:
            return v
        stripped = v.strip()
        if len(stripped) > 5000:
            raise ValueError("review_notes must be at most 5000 characters")
        return stripped or None


class IncidentAcknowledge(BaseModel):
    acknowledged_by: str
    notes: Optional[str] = None

    @field_validator("acknowledged_by")
    @classmethod
    def validate_acknowledged_by(cls, v):
        return _validate_non_empty_str(v, min_len=1, max_len=100)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v):
        if v is None:
            return v
        stripped = v.strip()
        if len(stripped) > 2000:
            raise ValueError("notes must be at most 2000 characters")
        return stripped or None


class IncidentTransfer(BaseModel):
    new_owner: str
    transferred_by: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("new_owner")
    @classmethod
    def validate_new_owner(cls, v):
        return _validate_non_empty_str(v, min_len=1, max_len=100)

    @field_validator("transferred_by")
    @classmethod
    def validate_transferred_by(cls, v):
        return _validate_non_empty_str(v, min_len=1, max_len=100)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v):
        if v is None:
            return v
        stripped = v.strip()
        if len(stripped) > 2000:
            raise ValueError("notes must be at most 2000 characters")
        return stripped or None


class IncidentResolve(BaseModel):
    resolved_by: str
    mark_for_review: bool = True
    review_notes: Optional[str] = None

    @field_validator("resolved_by")
    @classmethod
    def validate_resolved_by(cls, v):
        return _validate_non_empty_str(v, min_len=1, max_len=100)

    @field_validator("review_notes")
    @classmethod
    def validate_review_notes(cls, v):
        if v is None:
            return v
        stripped = v.strip()
        if len(stripped) > 5000:
            raise ValueError("review_notes must be at most 5000 characters")
        return stripped or None


class IncidentNoteCreate(BaseModel):
    author: str
    content: str
    action_type: str = "note"

    @field_validator("author")
    @classmethod
    def validate_author(cls, v):
        return _validate_non_empty_str(v, min_len=1, max_len=100)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        stripped = v.strip()
        if len(stripped) < 1:
            raise ValueError("content must not be empty")
        if len(stripped) > 5000:
            raise ValueError("content must be at most 5000 characters")
        return stripped

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, v):
        if v not in VALID_NOTE_ACTION_TYPES:
            raise ValueError(f"action_type must be one of {sorted(VALID_NOTE_ACTION_TYPES)}")
        return v


class IncidentListResponse(BaseModel):
    items: List[IncidentResponse] = []
    active_count: int = 0
    review_count: int = 0
    resolved_count: int = 0


class RegistrySourceCreate(BaseModel):
    name: str
    url: str
    pull_interval: int = Field(60, ge=10, le=3600)
    default_group_id: Optional[int] = None
    default_type: str = "http"
    default_interval: int = Field(30, ge=5, le=300)
    default_timeout: int = Field(5, ge=1, le=60)
    deprecate_after_hours: int = Field(24, ge=1, le=720)
    enabled: Optional[bool] = True
    headers: Optional[Dict[str, str]] = None


class RegistrySourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    pull_interval: Optional[int] = Field(None, ge=10, le=3600)
    default_group_id: Optional[int] = None
    default_type: Optional[str] = None
    default_interval: Optional[int] = Field(None, ge=5, le=300)
    default_timeout: Optional[int] = Field(None, ge=1, le=60)
    deprecate_after_hours: Optional[int] = Field(None, ge=1, le=720)
    enabled: Optional[bool] = None
    headers: Optional[Dict[str, str]] = None


class RegistrySourceResponse(BaseModel):
    id: int
    name: str
    url: str
    pull_interval: int
    default_group_id: Optional[int] = None
    default_group_name: Optional[str] = None
    default_type: str
    default_interval: int
    default_timeout: int
    deprecate_after_hours: int
    enabled: bool
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    target_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SyncEventDetailResponse(BaseModel):
    id: int
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    service_name: str
    service_address: str
    action: str
    detail: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SyncEventResponse(BaseModel):
    id: int
    source_id: int
    source_name: Optional[str] = None
    triggered_by: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    discovered_count: int
    new_count: int
    deprecated_count: int
    failed_count: int
    unchanged_count: int
    error_message: Optional[str] = None
    raw_service_count: int
    details: List[SyncEventDetailResponse] = []

    class Config:
        from_attributes = True


class SyncEventListResponse(BaseModel):
    items: List[SyncEventResponse] = []
    total: int = 0


class MaintenanceWindowCreate(BaseModel):
    target_id: Optional[int] = None
    group_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    reason: Optional[str] = None
    owner: Optional[str] = None
    created_by: Optional[str] = None

    @model_validator(mode='after')
    def check_target_or_group(self):
        if self.target_id is None and self.group_id is None:
            raise ValueError('必须指定 target_id 或 group_id 其中之一')
        if self.target_id is not None and self.group_id is not None:
            raise ValueError('不能同时指定 target_id 和 group_id')
        return self


class MaintenanceWindowUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    reason: Optional[str] = None
    owner: Optional[str] = None


class MaintenanceWindowExtend(BaseModel):
    end_time: datetime
    extension_reason: str

    @field_validator('extension_reason')
    @classmethod
    def extension_reason_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('延期原因不能为空')
        return v.strip()


class MaintenanceWindowCancel(BaseModel):
    cancelled_reason: Optional[str] = None


class MaintenanceWindowEventResponse(BaseModel):
    id: int
    window_id: int
    event_type: str
    message: str
    timestamp: datetime
    extra_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class MaintenanceWindowResponse(BaseModel):
    id: int
    target_id: int
    target_name: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    reason: Optional[str] = None
    owner: Optional[str] = None
    status: str
    is_cancelled: bool
    cancelled_at: Optional[datetime] = None
    cancelled_reason: Optional[str] = None
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    timeout_alert_sent: bool
    extension_reason: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    events: List[MaintenanceWindowEventResponse] = []

    class Config:
        from_attributes = True


class MaintenanceWindowListResponse(BaseModel):
    items: List[MaintenanceWindowResponse] = []
    total: int = 0


class MaintenanceWindowCalendarResponse(BaseModel):
    windows: List[MaintenanceWindowResponse] = []
    targets: List[Dict[str, Any]] = []


class DutySlotCreate(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=0, le=24)
    primary_person: str
    backup_person: str


class DutySlotResponse(BaseModel):
    id: int
    schedule_id: int
    day_of_week: int
    start_hour: int
    end_hour: int
    primary_person: str
    backup_person: str

    class Config:
        from_attributes = True


class DutySwapCreate(BaseModel):
    swap_date: datetime
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=0, le=24)
    original_person: str = Field(min_length=1, max_length=100)
    new_person: str = Field(min_length=1, max_length=100)
    role: str = "primary"
    reason: str = Field(min_length=1, max_length=500, description="换班原因不能为空")


class DutySwapResponse(BaseModel):
    id: int
    schedule_id: int
    swap_date: datetime
    start_hour: int
    end_hour: int
    original_person: str
    new_person: str
    role: str
    reason: str
    created_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DutyScheduleCreate(BaseModel):
    name: str
    group_id: Optional[int] = None
    is_default: bool = False
    timezone: str = "Asia/Shanghai"
    slots: List[DutySlotCreate] = []


class DutyScheduleUpdate(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None


class DutyScheduleResponse(BaseModel):
    id: int
    name: str
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    is_default: bool
    timezone: str
    slots: List[DutySlotResponse] = []
    swaps: List[DutySwapResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DispatchedAlertResponse(BaseModel):
    id: int
    alert_id: int
    schedule_id: int
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    primary_person: str
    backup_person: str
    assigned_to: Optional[str] = None
    dispatch_status: str
    dispatched_at: datetime
    primary_escalated_at: Optional[datetime] = None
    backup_escalated_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_summary: Optional[str] = None
    response_seconds: Optional[float] = None
    alert_target_name: Optional[str] = None
    alert_from_status: Optional[str] = None
    alert_to_status: Optional[str] = None
    alert_timestamp: Optional[datetime] = None

    class Config:
        from_attributes = True


class DispatchAcknowledge(BaseModel):
    acknowledged_by: str


class DispatchResolve(BaseModel):
    resolved_by: str
    resolution_summary: str


class DutyOverviewResponse(BaseModel):
    current_primary: Optional[str] = None
    current_backup: Optional[str] = None
    current_schedule_name: Optional[str] = None
    pending_alert_count: int = 0
    escalated_alert_count: int = 0
    unattended_alert_count: int = 0
    avg_response_seconds: Optional[float] = None
    my_pending_count: int = 0
    my_resolved_count: int = 0


class DutyCalendarSlot(BaseModel):
    day_of_week: int
    start_hour: int
    end_hour: int
    primary_person: str
    backup_person: str
    is_swapped: bool = False
    swap_reason: Optional[str] = None


class DutyCalendarDay(BaseModel):
    date: str
    day_of_week: int
    slots: List[DutyCalendarSlot] = []


class DutyCalendarWeek(BaseModel):
    week_start: str
    days: List[DutyCalendarDay] = []


class DutyPersonHistoryResponse(BaseModel):
    person: str
    total_dispatched: int = 0
    total_acknowledged: int = 0
    total_resolved: int = 0
    avg_response_seconds: Optional[float] = None
    alerts: List[DispatchedAlertResponse] = []


class CapacityConfigCreate(BaseModel):
    target_id: Optional[int] = None
    group_id: Optional[int] = None
    max_connections: Optional[int] = None
    max_latency_ms: float = 500.0
    max_throughput_rps: Optional[float] = None
    is_override: bool = False
    deviation_threshold_pct: Optional[float] = Field(None, ge=1, le=200)

    @model_validator(mode='after')
    def check_target_or_group(self):
        if self.target_id is None and self.group_id is None:
            raise ValueError('必须指定 target_id 或 group_id 其中之一')
        return self


class CapacityGroupConfigCreate(BaseModel):
    max_connections: Optional[int] = None
    max_latency_ms: float = 500.0
    max_throughput_rps: Optional[float] = None
    deviation_threshold_pct: Optional[float] = Field(None, ge=1, le=200)


class CapacityConfigUpdate(BaseModel):
    max_connections: Optional[int] = None
    max_latency_ms: Optional[float] = None
    max_throughput_rps: Optional[float] = None
    deviation_threshold_pct: Optional[float] = Field(None, ge=1, le=200)


class CapacityConfigResponse(BaseModel):
    id: int
    target_id: Optional[int] = None
    group_id: Optional[int] = None
    max_connections: Optional[int] = None
    max_latency_ms: float
    max_throughput_rps: Optional[float] = None
    is_override: bool
    deviation_threshold_pct: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CapacityBaselinePoint(BaseModel):
    day_of_week: int
    hour_of_day: int
    mean_utilization: float
    std_utilization: float
    min_utilization: float
    max_utilization: float
    percentile_25: float
    percentile_75: float
    sample_count: int


class CapacityBaselineBandPoint(BaseModel):
    hour: datetime
    baseline_mean: float
    baseline_lower: float
    baseline_upper: float
    lower_bound: float
    upper_bound: float


class CapacityDeviationEvent(BaseModel):
    hour: datetime
    current_utilization: float
    baseline_mean: float
    deviation_pct: float
    deviation_direction: str
    is_anomaly: bool


class CapacityDeviationAlertResponse(BaseModel):
    id: int
    target_id: int
    target_name: str
    hour: datetime
    current_utilization: float
    baseline_mean: float
    baseline_std: float
    deviation_pct: float
    deviation_direction: str
    threshold_pct: float
    is_active: bool
    resolved_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CapacityDeviationAnalysis(BaseModel):
    target_id: int
    target_name: str
    effective_threshold_pct: float
    current_deviation_pct: float
    current_deviation_direction: str
    is_current_anomaly: bool
    current_baseline_mean: float
    current_utilization: float
    events_24h: List[CapacityDeviationEvent] = []
    anomaly_count_24h: int = 0
    high_anomaly_count_24h: int = 0
    low_anomaly_count_24h: int = 0
    active_deviation_alerts: List[CapacityDeviationAlertResponse] = []


class CapacityHourlyPoint(BaseModel):
    hour: Optional[datetime] = None
    overall_utilization: float = 0.0
    latency_utilization: float = 0.0
    connection_utilization: float = 0.0
    throughput_utilization: float = 0.0


class CapacityHeatmapCell(BaseModel):
    date: str
    hour: int
    utilization: float


class CapacityPredictionResult(BaseModel):
    predicted_breach_85_at: Optional[datetime] = None
    predicted_breach_100_at: Optional[datetime] = None
    prediction_points: List[CapacityHourlyPoint] = []
    slope: float = 0.0
    current_trend: str = "stable"




class CapacityOverviewItem(BaseModel):
    target_id: int
    target_name: str
    group_name: Optional[str] = None
    current_water_level: float
    latency_utilization: float
    connection_utilization: float
    throughput_utilization: float
    water_level_status: str
    has_capacity_config: bool
    predicted_breach_85_at: Optional[datetime] = None
    predicted_breach_100_at: Optional[datetime] = None
    current_deviation_pct: Optional[float] = None
    current_deviation_direction: Optional[str] = None
    has_deviation_anomaly: bool = False
    effective_deviation_threshold: float = 30.0


class CapacityOverviewResponse(BaseModel):
    targets: List[CapacityOverviewItem] = []
    active_alerts: int = 0
    total_targets: int = 0
    configured_targets: int = 0


class CapacityPlanCreate(BaseModel):
    target_id: int
    planned_expansion_at: datetime
    target_capacity_multiplier: float = Field(2.0, ge=1.0, le=10.0)
    notes: Optional[str] = None


class CapacityPlanUpdate(BaseModel):
    planned_expansion_at: Optional[datetime] = None
    target_capacity_multiplier: Optional[float] = Field(None, ge=1.0, le=10.0)
    notes: Optional[str] = None


class CapacityPlanResponse(BaseModel):
    id: int
    target_id: int
    planned_expansion_at: datetime
    target_capacity_multiplier: float
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CapacityAlertResponse(BaseModel):
    id: int
    target_id: int
    target_name: str
    current_water_level: float
    predicted_breach_85_at: Optional[datetime] = None
    predicted_breach_100_at: Optional[datetime] = None
    suggested_expansion: Optional[float] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CapacityDetailResponse(BaseModel):
    target_id: int
    target_name: str
    group_name: Optional[str] = None
    config: Optional[CapacityConfigResponse] = None
    current_water_level: float
    water_level_status: str
    trend: List[CapacityHourlyPoint] = []
    heatmap: List[CapacityHeatmapCell] = []
    prediction: Optional[CapacityPredictionResult] = None
    plans: List[CapacityPlanResponse] = []
    alerts: List[CapacityAlertResponse] = []
    baseline_band: List[CapacityBaselineBandPoint] = []
    deviation_analysis: Optional[CapacityDeviationAnalysis] = None
    effective_deviation_threshold: float = 30.0


class AuditLogResponse(BaseModel):
    id: int
    operator: Optional[str] = None
    operation_type: str
    target_type: str
    target_id: Optional[int] = None
    target_name: Optional[str] = None
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    items: List[AuditLogResponse] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0


class ComplianceReportSummary(BaseModel):
    total_targets: int = 0
    total_alerts: int = 0
    total_audit_logs: int = 0
    total_config_changes: int = 0


class ProbeCoverageDetail(BaseModel):
    total_targets: int = 0
    active_targets: int = 0
    paused_targets: int = 0
    fully_covered: int = 0
    partially_covered: int = 0
    not_covered: int = 0
    coverage_rate: float = 0.0
    uncovered_targets: List[Dict[str, Any]] = []


class AlertResponseDetail(BaseModel):
    total_alerts: int = 0
    acknowledged_alerts: int = 0
    unacknowledged_alerts: int = 0
    acknowledgment_rate: float = 0.0
    avg_response_seconds: Optional[float] = None


class MttrDetail(BaseModel):
    total_incidents: int = 0
    avg_recovery_seconds: Optional[float] = None
    median_recovery_seconds: Optional[float] = None
    max_recovery_seconds: Optional[float] = None
    min_recovery_seconds: Optional[float] = None


class ConfigChangesDetail(BaseModel):
    total_changes: int = 0
    target_changes: int = 0
    group_changes: int = 0
    threshold_changes: int = 0
    maintenance_changes: int = 0
    duty_changes: int = 0


class TopChangedTarget(BaseModel):
    target_id: int
    target_name: str
    change_count: int


class ComplianceReportResponse(BaseModel):
    id: int
    report_type: str
    period_start: datetime
    period_end: datetime
    title: str
    summary: ComplianceReportSummary
    probe_coverage: ProbeCoverageDetail
    alert_response: AlertResponseDetail
    mttr: MttrDetail
    config_changes: ConfigChangesDetail
    top_changed_targets: List[TopChangedTarget] = []
    audit_log_count: int = 0
    generated_at: datetime
    generated_by: Optional[str] = None

    class Config:
        from_attributes = True


class ComplianceReportListResponse(BaseModel):
    items: List[ComplianceReportResponse] = []
    total: int = 0


class GenerateReportRequest(BaseModel):
    start_time: datetime
    end_time: datetime
    report_type: Optional[str] = "custom"
