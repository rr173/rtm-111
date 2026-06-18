from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class ObservationPoint(Base):
    __tablename__ = "observation_points"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    region = Column(String(100), nullable=False)
    status = Column(String(20), default="online")
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    description = Column(String(512), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    target_bindings = relationship("TargetObserverBinding", back_populates="observer", cascade="all, delete-orphan")
    probe_results = relationship("ObserverProbeResult", back_populates="observer", cascade="all, delete-orphan")


class TargetObserverBinding(Base):
    __tablename__ = "target_observer_bindings"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False)
    observer_id = Column(Integer, ForeignKey("observation_points.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    target = relationship("ProbeTarget", back_populates="observer_bindings")
    observer = relationship("ObservationPoint", back_populates="target_bindings")


class ObserverProbeResult(Base):
    __tablename__ = "observer_probe_results"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False, index=True)
    observer_id = Column(Integer, ForeignKey("observation_points.id"), nullable=False, index=True)
    round_id = Column(String(64), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    success = Column(Boolean, nullable=False)
    latency_ms = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)

    target = relationship("ProbeTarget", back_populates="observer_results")
    observer = relationship("ObservationPoint", back_populates="probe_results")


class ProbeGroup(Base):
    __tablename__ = "probe_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(512), nullable=True)
    color = Column(String(20), default="#3b82f6")
    degrade_threshold = Column(Integer, default=2)
    down_threshold = Column(Integer, default=5)
    success_threshold = Column(Integer, default=3)
    adaptive_enabled = Column(Boolean, default=False)
    slow_interval = Column(Integer, default=60)
    fast_interval = Column(Integer, default=5)
    silent_start = Column(String(5), nullable=True)
    silent_end = Column(String(5), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    targets = relationship("ProbeTarget", back_populates="group")


class ProbeRule(Base):
    __tablename__ = "probe_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(512), nullable=True)
    current_version_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    versions = relationship("ProbeRuleVersion", back_populates="rule", cascade="all, delete-orphan")
    targets = relationship("ProbeTarget", back_populates="rule")


class ProbeRuleVersion(Base):
    __tablename__ = "probe_rule_versions"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("probe_rules.id"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    execution_mode = Column(String(10), nullable=False, default="sequence")
    created_at = Column(DateTime, default=datetime.utcnow)

    rule = relationship("ProbeRule", back_populates="versions")
    steps = relationship("ProbeRuleStep", back_populates="version", cascade="all, delete-orphan")
    executions = relationship("ProbeRuleExecution", back_populates="version")


class ProbeRuleStep(Base):
    __tablename__ = "probe_rule_steps"

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("probe_rule_versions.id"), nullable=False)
    step_order = Column(Integer, nullable=False, default=0)
    name = Column(String(255), nullable=False)
    step_type = Column(String(30), nullable=False)
    config = Column(JSON, nullable=True)
    timeout = Column(Integer, nullable=False, default=5)
    pass_condition = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    version = relationship("ProbeRuleVersion", back_populates="steps")
    executions = relationship("ProbeRuleStepExecution", back_populates="step", cascade="all, delete-orphan")


class ProbeRuleExecution(Base):
    __tablename__ = "probe_rule_executions"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False)
    version_id = Column(Integer, ForeignKey("probe_rule_versions.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    success = Column(Boolean, nullable=False)
    latency_ms = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    failed_step_id = Column(Integer, nullable=True)

    target = relationship("ProbeTarget", back_populates="rule_executions")
    version = relationship("ProbeRuleVersion", back_populates="executions")
    step_executions = relationship("ProbeRuleStepExecution", back_populates="rule_execution", cascade="all, delete-orphan")


class ProbeRuleStepExecution(Base):
    __tablename__ = "probe_rule_step_executions"

    id = Column(Integer, primary_key=True, index=True)
    rule_execution_id = Column(Integer, ForeignKey("probe_rule_executions.id"), nullable=False)
    step_id = Column(Integer, ForeignKey("probe_rule_steps.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    success = Column(Boolean, nullable=False)
    latency_ms = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    raw_response = Column(Text, nullable=True)

    rule_execution = relationship("ProbeRuleExecution", back_populates="step_executions")
    step = relationship("ProbeRuleStep", back_populates="executions")


class ProbeTarget(Base):
    __tablename__ = "probe_targets"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("probe_groups.id"), nullable=True)
    rule_id = Column(Integer, ForeignKey("probe_rules.id"), nullable=True)
    name = Column(String(255), nullable=False)
    type = Column(String(10), nullable=False)
    address = Column(String(512), nullable=False)
    interval = Column(Integer, nullable=False, default=30)
    timeout = Column(Integer, nullable=False, default=5)
    expected_status = Column(String(50), nullable=True)
    paused = Column(Boolean, default=False)
    silenced = Column(Boolean, default=False)
    status = Column(String(20), default="healthy")
    cascade_affected = Column(Boolean, default=False)
    cascade_source_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=True)
    consecutive_failures = Column(Integer, default=0)
    consecutive_successes = Column(Integer, default=0)
    last_check = Column(DateTime, nullable=True)
    degrade_threshold = Column(Integer, nullable=True)
    down_threshold = Column(Integer, nullable=True)
    success_threshold = Column(Integer, nullable=True)
    adaptive_enabled = Column(Boolean, nullable=True)
    slow_interval = Column(Integer, nullable=True)
    fast_interval = Column(Integer, nullable=True)
    silent_start = Column(String(5), nullable=True)
    silent_end = Column(String(5), nullable=True)
    source_id = Column(Integer, ForeignKey("registry_sources.id"), nullable=True, index=True)
    deprecated = Column(Boolean, default=False)
    deprecated_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    group = relationship("ProbeGroup", back_populates="targets")
    rule = relationship("ProbeRule", back_populates="targets")
    results = relationship("ProbeResult", back_populates="target", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="target", cascade="all, delete-orphan")
    rule_executions = relationship("ProbeRuleExecution", back_populates="target", cascade="all, delete-orphan")
    cascade_source = relationship("ProbeTarget", remote_side=[id], foreign_keys=[cascade_source_id])
    downstream_dependencies = relationship(
        "Dependency",
        foreign_keys="Dependency.upstream_id",
        back_populates="upstream_target",
        cascade="all, delete-orphan"
    )
    upstream_dependencies = relationship(
        "Dependency",
        foreign_keys="Dependency.downstream_id",
        back_populates="downstream_target",
        cascade="all, delete-orphan"
    )
    observer_bindings = relationship("TargetObserverBinding", back_populates="target", cascade="all, delete-orphan")
    observer_results = relationship("ObserverProbeResult", back_populates="target", cascade="all, delete-orphan")


class Dependency(Base):
    __tablename__ = "dependencies"

    id = Column(Integer, primary_key=True, index=True)
    upstream_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False)
    downstream_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    upstream_target = relationship(
        "ProbeTarget",
        foreign_keys=[upstream_id],
        back_populates="downstream_dependencies"
    )
    downstream_target = relationship(
        "ProbeTarget",
        foreign_keys=[downstream_id],
        back_populates="upstream_dependencies"
    )


class ProbeResult(Base):
    __tablename__ = "probe_results"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    success = Column(Boolean, nullable=False)
    latency_ms = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)

    target = relationship("ProbeTarget", back_populates="results")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    from_status = Column(String(20), nullable=False)
    to_status = Column(String(20), nullable=False)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)

    target = relationship("ProbeTarget", back_populates="alerts")


class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1024), nullable=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)
    target_count = Column(Integer, default=0)
    data_point_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    data = relationship("SnapshotData", back_populates="snapshot", cascade="all, delete-orphan")
    alerts = relationship("SnapshotAlert", back_populates="snapshot", cascade="all, delete-orphan")


class SnapshotData(Base):
    __tablename__ = "snapshot_data"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("snapshots.id"), nullable=False, index=True)
    target_id = Column(Integer, nullable=False, index=True)
    target_name = Column(String(255), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    status = Column(String(20), nullable=False)
    latency_ms = Column(Float, nullable=True)
    success = Column(Boolean, nullable=False)
    consecutive_failures = Column(Integer, default=0)
    consecutive_successes = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    snapshot = relationship("Snapshot", back_populates="data")


class SnapshotAlert(Base):
    __tablename__ = "snapshot_alerts"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("snapshots.id"), nullable=False, index=True)
    target_id = Column(Integer, nullable=False, index=True)
    target_name = Column(String(255), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    from_status = Column(String(20), nullable=False)
    to_status = Column(String(20), nullable=False)

    snapshot = relationship("Snapshot", back_populates="alerts")


class Change(Base):
    __tablename__ = "changes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1024), nullable=True)
    planned_time = Column(DateTime, nullable=False, index=True)
    status = Column(String(20), default="pending", index=True)
    start_time = Column(DateTime, nullable=True, index=True)
    end_time = Column(DateTime, nullable=True, index=True)
    baseline_snapshot_id = Column(Integer, ForeignKey("snapshots.id"), nullable=True)
    result_snapshot_id = Column(Integer, ForeignKey("snapshots.id"), nullable=True)
    conclusion = Column(String(20), nullable=True)
    conclusion_reason = Column(String(1024), nullable=True)
    notes = Column(String(2048), nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    baseline_snapshot = relationship("Snapshot", foreign_keys=[baseline_snapshot_id])
    result_snapshot = relationship("Snapshot", foreign_keys=[result_snapshot_id])
    targets = relationship("ChangeTarget", back_populates="change", cascade="all, delete-orphan")
    events = relationship("ChangeEvent", back_populates="change", cascade="all, delete-orphan")


class ChangeTarget(Base):
    __tablename__ = "change_targets"

    id = Column(Integer, primary_key=True, index=True)
    change_id = Column(Integer, ForeignKey("changes.id"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    change = relationship("Change", back_populates="targets")
    target = relationship("ProbeTarget")


class ChangeEvent(Base):
    __tablename__ = "change_events"

    id = Column(Integer, primary_key=True, index=True)
    change_id = Column(Integer, ForeignKey("changes.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    message = Column(String(1024), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    data = Column(JSON, nullable=True)

    change = relationship("Change", back_populates="events")


class SLOTarget(Base):
    __tablename__ = "slo_targets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1024), nullable=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=True)
    group_id = Column(Integer, ForeignKey("probe_groups.id"), nullable=True)
    slo_type = Column(String(30), nullable=False, default="availability")
    slo_target = Column(Float, nullable=False, default=99.9)
    latency_threshold_ms = Column(Float, nullable=True)
    window_days = Column(Integer, nullable=False, default=30)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    target = relationship("ProbeTarget", backref="slo_bindings")
    group = relationship("ProbeGroup", backref="slo_bindings")


class SLOBudgetSnapshot(Base):
    __tablename__ = "slo_budget_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    slo_id = Column(Integer, ForeignKey("slo_targets.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    total_budget = Column(Float, nullable=False)
    budget_consumed = Column(Float, nullable=False)
    budget_remaining = Column(Float, nullable=False)
    current_value = Column(Float, nullable=False)
    service_fault = Column(Float, default=0)
    regional_anomaly = Column(Float, default=0)
    dependency_cascade = Column(Float, default=0)
    change_induced = Column(Float, default=0)

    slo = relationship("SLOTarget", backref="snapshots")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(20), default="warning")
    status = Column(String(30), default="active", index=True)
    first_anomaly_at = Column(DateTime, nullable=False, index=True)
    last_anomaly_at = Column(DateTime, nullable=False)
    recovered_at = Column(DateTime, nullable=True, index=True)
    bleed_over_until = Column(DateTime, nullable=True)
    mitigated = Column(Boolean, default=False)
    mitigated_at = Column(DateTime, nullable=True)
    owner = Column(String(100), nullable=True)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    needs_review = Column(Boolean, default=False)
    review_notes = Column(Text, nullable=True)
    parent_incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent_incident = relationship("Incident", remote_side=[id], foreign_keys=[parent_incident_id])
    targets = relationship("IncidentTarget", back_populates="incident", cascade="all, delete-orphan")
    alerts = relationship("IncidentAlert", back_populates="incident", cascade="all, delete-orphan")
    timeline = relationship("IncidentTimeline", back_populates="incident", cascade="all, delete-orphan", order_by="IncidentTimeline.timestamp.asc()")
    notes = relationship("IncidentNote", back_populates="incident", cascade="all, delete-orphan", order_by="IncidentNote.created_at.asc()")


class IncidentTarget(Base):
    __tablename__ = "incident_targets"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False, index=True)
    role = Column(String(30), default="affected")
    first_alert_at = Column(DateTime, nullable=True)
    last_alert_at = Column(DateTime, nullable=True)
    max_severity = Column(String(20), default="warning")
    created_at = Column(DateTime, default=datetime.utcnow)

    incident = relationship("Incident", back_populates="targets")
    target = relationship("ProbeTarget")


class IncidentAlert(Base):
    __tablename__ = "incident_alerts"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    incident = relationship("Incident", back_populates="alerts")
    alert = relationship("Alert")


class IncidentTimeline(Base):
    __tablename__ = "incident_timeline"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_type = Column(String(50), nullable=False)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(20), nullable=True)
    extra_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    incident = relationship("Incident", back_populates="timeline")


class IncidentNote(Base):
    __tablename__ = "incident_notes"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False)
    author = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    action_type = Column(String(30), default="note")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    incident = relationship("Incident", back_populates="notes")


class RegistrySource(Base):
    __tablename__ = "registry_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(1024), nullable=False)
    pull_interval = Column(Integer, nullable=False, default=60)
    default_group_id = Column(Integer, ForeignKey("probe_groups.id"), nullable=True)
    default_type = Column(String(10), nullable=False, default="http")
    default_interval = Column(Integer, nullable=False, default=30)
    default_timeout = Column(Integer, nullable=False, default=5)
    deprecate_after_hours = Column(Integer, nullable=False, default=24)
    enabled = Column(Boolean, default=True)
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(20), nullable=True)
    headers = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    default_group = relationship("ProbeGroup")
    sync_events = relationship("SyncEvent", back_populates="source", cascade="all, delete-orphan")


class SyncEvent(Base):
    __tablename__ = "sync_events"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("registry_sources.id"), nullable=False, index=True)
    triggered_by = Column(String(20), nullable=False, default="auto")
    status = Column(String(20), nullable=False, default="running")
    started_at = Column(DateTime, default=datetime.utcnow, index=True)
    finished_at = Column(DateTime, nullable=True)
    discovered_count = Column(Integer, default=0)
    new_count = Column(Integer, default=0)
    deprecated_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    unchanged_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    raw_service_count = Column(Integer, default=0)

    source = relationship("RegistrySource", back_populates="sync_events")
    details = relationship("SyncEventDetail", back_populates="event", cascade="all, delete-orphan")


class SyncEventDetail(Base):
    __tablename__ = "sync_event_details"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("sync_events.id"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=True, index=True)
    service_name = Column(String(255), nullable=False)
    service_address = Column(String(512), nullable=False)
    action = Column(String(20), nullable=False)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("SyncEvent", back_populates="details")
    target = relationship("ProbeTarget")


class RecordingSession(Base):
    __tablename__ = "recording_sessions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1024), nullable=True)
    tags = Column(JSON, default=list)
    status = Column(String(20), default="recording", index=True)
    started_at = Column(DateTime, nullable=False, index=True)
    ended_at = Column(DateTime, nullable=True, index=True)
    duration_seconds = Column(Integer, default=0)
    recorded_count = Column(Integer, default=0)
    target_count = Column(Integer, default=0)
    filter_target_ids = Column(JSON, nullable=True)
    filter_group_ids = Column(JSON, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    events = relationship("RecordingEvent", back_populates="session", cascade="all, delete-orphan")
    pre_playback_snapshot = relationship(
        "PlaybackSnapshot",
        back_populates="session",
        foreign_keys="PlaybackSnapshot.session_id",
        uselist=False,
        cascade="all, delete-orphan"
    )


class RecordingEvent(Base):
    __tablename__ = "recording_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("recording_sessions.id"), nullable=False, index=True)
    event_type = Column(String(30), nullable=False, index=True)
    target_id = Column(Integer, nullable=True, index=True)
    target_name = Column(String(255), nullable=True)
    relative_time_ms = Column(Integer, nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("RecordingSession", back_populates="events")


class PlaybackSnapshot(Base):
    __tablename__ = "playback_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("recording_sessions.id"), nullable=False, unique=True, index=True)
    targets_snapshot = Column(JSON, nullable=False)
    alerts_snapshot = Column(JSON, nullable=False)
    incidents_snapshot = Column(JSON, nullable=False)
    groups_snapshot = Column(JSON, nullable=False)
    dependencies_snapshot = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("RecordingSession", back_populates="pre_playback_snapshot", foreign_keys=[session_id])


class MaintenanceWindow(Base):
    __tablename__ = "maintenance_windows"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("probe_groups.id"), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)
    reason = Column(String(255), nullable=True)
    owner = Column(String(100), nullable=True)
    status = Column(String(20), default="scheduled", index=True)
    is_cancelled = Column(Boolean, default=False)
    cancelled_at = Column(DateTime, nullable=True)
    cancelled_reason = Column(String(512), nullable=True)
    actual_start_time = Column(DateTime, nullable=True)
    actual_end_time = Column(DateTime, nullable=True)
    timeout_alert_sent = Column(Boolean, default=False)
    extension_reason = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    target = relationship("ProbeTarget", backref="maintenance_windows")
    group = relationship("ProbeGroup", backref="maintenance_windows")
    events = relationship("MaintenanceWindowEvent", back_populates="window", cascade="all, delete-orphan")


class MaintenanceWindowEvent(Base):
    __tablename__ = "maintenance_window_events"

    id = Column(Integer, primary_key=True, index=True)
    window_id = Column(Integer, ForeignKey("maintenance_windows.id"), nullable=False, index=True)
    event_type = Column(String(30), nullable=False)
    message = Column(String(512), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    extra_data = Column(JSON, nullable=True)

    window = relationship("MaintenanceWindow", back_populates="events")


class DutySchedule(Base):
    __tablename__ = "duty_schedules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    group_id = Column(Integer, ForeignKey("probe_groups.id"), nullable=True, unique=True, index=True)
    is_default = Column(Boolean, default=False)
    timezone = Column(String(50), default="UTC")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    group = relationship("ProbeGroup", backref="duty_schedule")
    slots = relationship("DutySlot", back_populates="schedule", cascade="all, delete-orphan")
    swaps = relationship("DutySwap", back_populates="schedule", cascade="all, delete-orphan")
    dispatched_alerts = relationship("DispatchedAlert", back_populates="schedule", cascade="all, delete-orphan")


class DutySlot(Base):
    __tablename__ = "duty_slots"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("duty_schedules.id"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)
    start_hour = Column(Integer, nullable=False)
    end_hour = Column(Integer, nullable=False)
    primary_person = Column(String(100), nullable=False)
    backup_person = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    schedule = relationship("DutySchedule", back_populates="slots")


class DutySwap(Base):
    __tablename__ = "duty_swaps"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("duty_schedules.id"), nullable=False, index=True)
    swap_date = Column(DateTime, nullable=False, index=True)
    start_hour = Column(Integer, nullable=False)
    end_hour = Column(Integer, nullable=False)
    original_person = Column(String(100), nullable=False)
    new_person = Column(String(100), nullable=False)
    role = Column(String(20), default="primary")
    reason = Column(Text, nullable=False)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    schedule = relationship("DutySchedule", back_populates="swaps")


class CapacityConfig(Base):
    __tablename__ = "capacity_configs"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=True, index=True)
    group_id = Column(Integer, ForeignKey("probe_groups.id"), nullable=True, index=True)
    max_connections = Column(Integer, nullable=True)
    max_latency_ms = Column(Float, nullable=False, default=500.0)
    max_throughput_rps = Column(Float, nullable=True)
    is_override = Column(Boolean, default=False)
    deviation_threshold_pct = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    target = relationship("ProbeTarget", backref="capacity_config")
    group = relationship("ProbeGroup", backref="capacity_config")


class CapacityBaseline(Base):
    __tablename__ = "capacity_baselines"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False, index=True)
    hour_of_day = Column(Integer, nullable=False, index=True)
    mean_utilization = Column(Float, nullable=False, default=0.0)
    std_utilization = Column(Float, nullable=False, default=0.0)
    min_utilization = Column(Float, nullable=False, default=0.0)
    max_utilization = Column(Float, nullable=False, default=0.0)
    percentile_25 = Column(Float, nullable=False, default=0.0)
    percentile_75 = Column(Float, nullable=False, default=0.0)
    sample_count = Column(Integer, nullable=False, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    target = relationship("ProbeTarget", backref="capacity_baselines")


class CapacityDeviationAlert(Base):
    __tablename__ = "capacity_deviation_alerts"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False, index=True)
    target_name = Column(String(255), nullable=False)
    hour = Column(DateTime, nullable=False, index=True)
    current_utilization = Column(Float, nullable=False)
    baseline_mean = Column(Float, nullable=False)
    baseline_std = Column(Float, nullable=False)
    deviation_pct = Column(Float, nullable=False)
    deviation_direction = Column(String(10), nullable=False)
    threshold_pct = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    target = relationship("ProbeTarget", backref="capacity_deviation_alerts")


class CapacityHourlySnapshot(Base):
    __tablename__ = "capacity_hourly_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False, index=True)
    hour = Column(DateTime, nullable=False, index=True)
    avg_latency_ms = Column(Float, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=1.0)
    request_count = Column(Integer, nullable=False, default=0)
    latency_utilization = Column(Float, nullable=False, default=0)
    connection_utilization = Column(Float, nullable=False, default=0)
    throughput_utilization = Column(Float, nullable=False, default=0)
    overall_utilization = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    target = relationship("ProbeTarget", backref="capacity_snapshots")


class CapacityAlert(Base):
    __tablename__ = "capacity_alerts"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False, index=True)
    target_name = Column(String(255), nullable=False)
    current_water_level = Column(Float, nullable=False)
    predicted_breach_85_at = Column(DateTime, nullable=True)
    predicted_breach_100_at = Column(DateTime, nullable=True)
    suggested_expansion = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    target = relationship("ProbeTarget", backref="capacity_alerts")


class CapacityPlan(Base):
    __tablename__ = "capacity_plans"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False, index=True)
    planned_expansion_at = Column(DateTime, nullable=False)
    target_capacity_multiplier = Column(Float, nullable=False, default=2.0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    target = relationship("ProbeTarget", backref="capacity_plan")


class DispatchedAlert(Base):
    __tablename__ = "dispatched_alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    schedule_id = Column(Integer, ForeignKey("duty_schedules.id"), nullable=False, index=True)
    group_id = Column(Integer, ForeignKey("probe_groups.id"), nullable=True, index=True)
    primary_person = Column(String(100), nullable=False)
    backup_person = Column(String(100), nullable=False)
    assigned_to = Column(String(100), nullable=True, index=True)
    dispatch_status = Column(String(30), default="dispatched", index=True)
    dispatched_at = Column(DateTime, default=datetime.utcnow, index=True)
    primary_escalated_at = Column(DateTime, nullable=True)
    backup_escalated_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(100), nullable=True)
    resolution_summary = Column(Text, nullable=True)
    response_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    alert = relationship("Alert", backref="dispatch")
    schedule = relationship("DutySchedule", back_populates="dispatched_alerts")
    group = relationship("ProbeGroup", backref="dispatched_alerts")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    operator = Column(String(100), nullable=True, index=True)
    operation_type = Column(String(50), nullable=False, index=True)
    target_type = Column(String(50), nullable=False, index=True)
    target_id = Column(Integer, nullable=True, index=True)
    target_name = Column(String(255), nullable=True, index=True)
    old_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    description = Column(String(512), nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ComplianceReport(Base):
    __tablename__ = "compliance_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String(20), nullable=False, index=True)
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(JSON, nullable=False)
    probe_coverage = Column(JSON, nullable=False)
    alert_response = Column(JSON, nullable=False)
    mttr = Column(JSON, nullable=False)
    config_changes = Column(JSON, nullable=False)
    top_changed_targets = Column(JSON, nullable=False)
    audit_log_count = Column(Integer, default=0)
    generated_at = Column(DateTime, default=datetime.utcnow, index=True)
    generated_by = Column(String(100), nullable=True)

    class Config:
        from_attributes = True


class HealthScore(Base):
    __tablename__ = "health_scores"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False, unique=True, index=True)
    target_name = Column(String(255), nullable=False)
    group_id = Column(Integer, ForeignKey("probe_groups.id"), nullable=True)
    group_name = Column(String(255), nullable=True)
    overall_score = Column(Float, nullable=False, default=0)
    availability_score = Column(Float, nullable=False, default=0)
    latency_score = Column(Float, nullable=False, default=0)
    alert_score = Column(Float, nullable=False, default=0)
    stability_score = Column(Float, nullable=False, default=0)
    availability_weight = Column(Float, nullable=False, default=0.4)
    latency_weight = Column(Float, nullable=False, default=0.2)
    alert_weight = Column(Float, nullable=False, default=0.2)
    stability_weight = Column(Float, nullable=False, default=0.2)
    availability_7d = Column(Float, nullable=True)
    avg_latency_ms = Column(Float, nullable=True)
    latency_threshold_ms = Column(Float, nullable=True)
    alert_count_7d = Column(Integer, nullable=True)
    consecutive_healthy_hours = Column(Integer, nullable=True)
    previous_score = Column(Float, nullable=True)
    score_trend = Column(String(20), default="flat")
    last_calculated_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    target = relationship("ProbeTarget", backref="health_score")


class HealthScoreHistory(Base):
    __tablename__ = "health_score_history"

    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False, index=True)
    target_name = Column(String(255), nullable=False)
    group_id = Column(Integer, ForeignKey("probe_groups.id"), nullable=True)
    group_name = Column(String(255), nullable=True)
    overall_score = Column(Float, nullable=False, default=0)
    availability_score = Column(Float, nullable=False, default=0)
    latency_score = Column(Float, nullable=False, default=0)
    alert_score = Column(Float, nullable=False, default=0)
    stability_score = Column(Float, nullable=False, default=0)
    availability_7d = Column(Float, nullable=True)
    avg_latency_ms = Column(Float, nullable=True)
    alert_count_7d = Column(Integer, nullable=True)
    consecutive_healthy_hours = Column(Integer, nullable=True)
    snapshot_hour = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    target = relationship("ProbeTarget", backref="health_score_history")


class HealthRankingSnapshot(Base):
    __tablename__ = "health_ranking_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_time = Column(DateTime, nullable=False, index=True)
    total_targets = Column(Integer, nullable=False, default=0)
    avg_score = Column(Float, nullable=False, default=0)
    data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class SLAContract(Base):
    __tablename__ = "sla_contracts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    party_a = Column(String(255), nullable=False)
    party_b = Column(String(255), nullable=False)
    effective_date = Column(DateTime, nullable=False, index=True)
    expiry_date = Column(DateTime, nullable=False, index=True)
    monthly_availability_target = Column(Float, nullable=False, default=99.95)
    max_single_outage_minutes = Column(Integer, nullable=False, default=30)
    max_monthly_outage_minutes = Column(Integer, nullable=False, default=22)
    penalty_rate = Column(Float, nullable=False, default=0.1)
    status = Column(String(20), default="active", index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    targets = relationship("SLAContractTarget", back_populates="contract", cascade="all, delete-orphan")
    violations = relationship("SLAViolation", back_populates="contract", cascade="all, delete-orphan")
    monthly_stats = relationship("SLAMonthlyPerformance", back_populates="contract", cascade="all, delete-orphan")


class SLAContractTarget(Base):
    __tablename__ = "sla_contract_targets"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("sla_contracts.id"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    contract = relationship("SLAContract", back_populates="targets")
    target = relationship("ProbeTarget", backref="sla_contracts")


class SLAViolation(Base):
    __tablename__ = "sla_violations"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("sla_contracts.id"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("probe_targets.id"), nullable=False, index=True)
    violation_type = Column(String(30), nullable=False, index=True)
    detected_at = Column(DateTime, nullable=False, index=True)
    actual_duration_minutes = Column(Float, nullable=False)
    exceeded_minutes = Column(Float, nullable=False)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True)
    estimated_penalty = Column(Float, nullable=False, default=0)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    contract = relationship("SLAContract", back_populates="violations")
    target = relationship("ProbeTarget", backref="sla_violations")
    alert = relationship("Alert", backref="sla_violations")
    incident = relationship("Incident", backref="sla_violations")


class SLAMonthlyPerformance(Base):
    __tablename__ = "sla_monthly_performance"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer, ForeignKey("sla_contracts.id"), nullable=False, index=True)
    month = Column(String(7), nullable=False, index=True)
    availability_pct = Column(Float, nullable=False, default=100.0)
    total_outage_minutes = Column(Float, nullable=False, default=0)
    violation_count = Column(Integer, nullable=False, default=0)
    single_outage_violations = Column(Integer, nullable=False, default=0)
    monthly_outage_violations = Column(Integer, nullable=False, default=0)
    total_penalty = Column(Float, nullable=False, default=0)
    status = Column(String(20), default="compliant", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contract = relationship("SLAContract", back_populates="monthly_stats")
