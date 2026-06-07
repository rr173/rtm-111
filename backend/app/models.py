from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class ProbeTarget(Base):
    __tablename__ = "probe_targets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(10), nullable=False)
    address = Column(String(512), nullable=False)
    interval = Column(Integer, nullable=False, default=30)
    timeout = Column(Integer, nullable=False, default=5)
    expected_status = Column(String(50), nullable=True)
    paused = Column(Boolean, default=False)
    silenced = Column(Boolean, default=False)
    status = Column(String(20), default="healthy")
    consecutive_failures = Column(Integer, default=0)
    consecutive_successes = Column(Integer, default=0)
    last_check = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    results = relationship("ProbeResult", back_populates="target", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="target", cascade="all, delete-orphan")


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
