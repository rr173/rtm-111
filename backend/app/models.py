from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


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
