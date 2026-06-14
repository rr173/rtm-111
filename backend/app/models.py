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
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False, index=True)
    author = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    action_type = Column(String(30), default="note")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    incident = relationship("Incident", back_populates="notes")
