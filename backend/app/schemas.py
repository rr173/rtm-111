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


class IncidentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    mitigated: Optional[bool] = None
    owner: Optional[str] = None
    needs_review: Optional[bool] = None
    review_notes: Optional[str] = None


class IncidentAcknowledge(BaseModel):
    acknowledged_by: str
    notes: Optional[str] = None


class IncidentTransfer(BaseModel):
    new_owner: str
    transferred_by: Optional[str] = None
    notes: Optional[str] = None


class IncidentResolve(BaseModel):
    resolved_by: str
    mark_for_review: bool = True
    review_notes: Optional[str] = None


class IncidentNoteCreate(BaseModel):
    author: str
    content: str
    action_type: str = "note"


class IncidentListResponse(BaseModel):
    items: List[IncidentResponse] = []
    active_count: int = 0
    review_count: int = 0
    resolved_count: int = 0
