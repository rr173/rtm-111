from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from typing import List, Set, Optional, Dict, Any
from datetime import datetime, timedelta
from collections import deque

from .database import engine, get_db, Base
from .models import (
    ProbeTarget, ProbeResult, Alert, ProbeGroup, Dependency,
    ProbeRule, ProbeRuleVersion, ProbeRuleStep,
    ProbeRuleExecution, ProbeRuleStepExecution,
    Snapshot, SnapshotData, SnapshotAlert,
    ObservationPoint, TargetObserverBinding, ObserverProbeResult,
    Change, ChangeTarget, ChangeEvent,
    SLOTarget, SLOBudgetSnapshot,
    Incident, IncidentTarget, IncidentAlert, IncidentTimeline, IncidentNote,
    RegistrySource, SyncEvent, SyncEventDetail,
    MaintenanceWindow, MaintenanceWindowEvent,
)
from .schemas import (
    ProbeTargetCreate, ProbeTargetUpdate, ProbeTargetResponse,
    ProbeResultResponse, AlertResponse, AlertAcknowledge,
    ProbeGroupCreate, ProbeGroupUpdate, ProbeGroupResponse,
    ProbeGroupWithTargetsResponse,
    DependencyCreate, DependencyUpdate, DependencyResponse,
    DependencyWithNamesResponse, CascadeSimulationResponse,
    ProbeRuleCreate, ProbeRuleUpdate, ProbeRuleResponse,
    ProbeRuleVersionResponse, ProbeRuleStepResponse,
    ProbeRuleExecutionResponse, ProbeRuleStepExecutionResponse,
    ProbeRuleStepHistoryResponse,
    SnapshotCreate, SnapshotUpdate, SnapshotResponse,
    SnapshotDetailResponse, SnapshotComparisonResponse,
    ObservationPointCreate, ObservationPointUpdate, ObservationPointResponse,
    TargetObserverBindingCreate,
    ChangeCreate, ChangeUpdate, ChangeResponse,
    ChangeObservationResponse, ChangeComparisonResponse,
    TargetActiveChange,
    SLOTargetCreate, SLOTargetUpdate, SLOTargetResponse,
    SLOBudgetResponse, SLOBudgetPoint, SLOBudgetAttribution,
    SLOBudgetOverviewItem, SLOPredictionResponse,
    IncidentResponse, IncidentUpdate, IncidentAcknowledge, IncidentTransfer, IncidentResolve,
    IncidentNoteCreate, IncidentListResponse,
    IncidentTargetInfo, IncidentAlertInfo, IncidentTimelineEvent,
    IncidentNoteInfo, IncidentDependencyInfo, IncidentRegionDivergence,
    IncidentSLOBudgetRisk,
    RegistrySourceCreate, RegistrySourceUpdate, RegistrySourceResponse,
    SyncEventDetailResponse, SyncEventResponse, SyncEventListResponse,
    MaintenanceWindowCreate, MaintenanceWindowUpdate, MaintenanceWindowResponse,
    MaintenanceWindowListResponse, MaintenanceWindowCalendarResponse,
    MaintenanceWindowExtend, MaintenanceWindowCancel, MaintenanceWindowEventResponse,
)
from .observer_engine import observer_engine
from .probe_engine import probe_engine
from .sync_engine import sync_engine
from .websocket_manager import manager, get_target_history
from .recording_engine import recording_engine
from .playback_engine import playback_engine
from .maintenance_engine import maintenance_engine
from pydantic import BaseModel
from typing import List as TypingList


def _enrich_target(target: ProbeTarget, db: Session = None) -> dict:
    strategy = probe_engine._get_effective_strategy(target)
    current_interval = probe_engine._get_effective_interval(target)
    in_silent = probe_engine._is_in_silent_window(target)
    next_probe_at = datetime.utcnow() + timedelta(seconds=current_interval)

    cascade_source_name = None
    if target.cascade_source_id and target.cascade_source:
        cascade_source_name = target.cascade_source.name
    elif target.cascade_source_id and db:
        source = db.query(ProbeTarget).filter(ProbeTarget.id == target.cascade_source_id).first()
        if source:
            cascade_source_name = source.name

    rule_name = None
    if target.rule_id and target.rule:
        rule_name = target.rule.name

    source_name = None
    if target.source_id:
        rs = db.query(RegistrySource).filter(RegistrySource.id == target.source_id).first() if db else None
        if rs:
            source_name = rs.name

    return {
        "id": target.id,
        "group_id": target.group_id,
        "rule_id": target.rule_id,
        "rule_name": rule_name,
        "name": target.name,
        "type": target.type,
        "address": target.address,
        "interval": target.interval,
        "timeout": target.timeout,
        "expected_status": target.expected_status,
        "paused": target.paused,
        "silenced": target.silenced,
        "status": target.status,
        "cascade_affected": target.cascade_affected,
        "cascade_source_id": target.cascade_source_id,
        "cascade_source_name": cascade_source_name,
        "consecutive_failures": target.consecutive_failures,
        "consecutive_successes": target.consecutive_successes,
        "last_check": target.last_check,
        "degrade_threshold": target.degrade_threshold,
        "down_threshold": target.down_threshold,
        "success_threshold": target.success_threshold,
        "adaptive_enabled": strategy["adaptive_enabled"],
        "slow_interval": strategy["slow_interval"],
        "fast_interval": strategy["fast_interval"],
        "silent_start": strategy["silent_start"],
        "silent_end": strategy["silent_end"],
        "source_id": target.source_id,
        "source_name": source_name,
        "deprecated": target.deprecated or False,
        "deprecated_at": target.deprecated_at,
        "last_seen_at": target.last_seen_at,
        "current_interval": current_interval,
        "next_probe_at": next_probe_at,
        "in_silent_window": in_silent,
        "created_at": target.created_at,
    }


def _create_tables():
    Base.metadata.create_all(bind=engine)


def _migrate_database():
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            result = conn.execute(text("PRAGMA table_info(probe_groups)"))
            columns = [row[1] for row in result.fetchall()]

            group_new_columns = [
                ("adaptive_enabled", "INTEGER DEFAULT 0"),
                ("slow_interval", "INTEGER DEFAULT 60"),
                ("fast_interval", "INTEGER DEFAULT 5"),
                ("silent_start", "VARCHAR(5)"),
                ("silent_end", "VARCHAR(5)"),
            ]
            for col_name, col_def in group_new_columns:
                if col_name not in columns:
                    conn.execute(text(f"ALTER TABLE probe_groups ADD COLUMN {col_name} {col_def}"))
                    print(f"Added column {col_name} to probe_groups")

            result = conn.execute(text("PRAGMA table_info(probe_targets)"))
            columns = [row[1] for row in result.fetchall()]

            target_new_columns = [
                ("adaptive_enabled", "INTEGER DEFAULT 0"),
                ("slow_interval", "INTEGER DEFAULT 60"),
                ("fast_interval", "INTEGER DEFAULT 5"),
                ("silent_start", "VARCHAR(5)"),
                ("silent_end", "VARCHAR(5)"),
                ("cascade_affected", "INTEGER DEFAULT 0"),
                ("cascade_source_id", "INTEGER"),
                ("rule_id", "INTEGER"),
            ]
            for col_name, col_def in target_new_columns:
                if col_name not in columns:
                    conn.execute(text(f"ALTER TABLE probe_targets ADD COLUMN {col_name} {col_def}"))
                    print(f"Added column {col_name} to probe_targets")

            rule_tables = {
                "probe_rules": """
                    CREATE TABLE probe_rules (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(255) NOT NULL,
                        description VARCHAR(512),
                        current_version_id INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                "probe_rule_versions": """
                    CREATE TABLE probe_rule_versions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rule_id INTEGER NOT NULL,
                        version INTEGER NOT NULL DEFAULT 1,
                        execution_mode VARCHAR(10) NOT NULL DEFAULT 'sequence',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (rule_id) REFERENCES probe_rules(id) ON DELETE CASCADE
                    )
                """,
                "probe_rule_steps": """
                    CREATE TABLE probe_rule_steps (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        version_id INTEGER NOT NULL,
                        step_order INTEGER NOT NULL DEFAULT 0,
                        name VARCHAR(255) NOT NULL,
                        step_type VARCHAR(30) NOT NULL,
                        config TEXT,
                        timeout INTEGER NOT NULL DEFAULT 5,
                        pass_condition TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (version_id) REFERENCES probe_rule_versions(id) ON DELETE CASCADE
                    )
                """,
                "probe_rule_executions": """
                    CREATE TABLE probe_rule_executions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        target_id INTEGER NOT NULL,
                        version_id INTEGER NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        success INTEGER NOT NULL,
                        latency_ms REAL,
                        error_message TEXT,
                        failed_step_id INTEGER,
                        FOREIGN KEY (target_id) REFERENCES probe_targets(id) ON DELETE CASCADE,
                        FOREIGN KEY (version_id) REFERENCES probe_rule_versions(id)
                    )
                """,
                "probe_rule_step_executions": """
                    CREATE TABLE probe_rule_step_executions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rule_execution_id INTEGER NOT NULL,
                        step_id INTEGER NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        success INTEGER NOT NULL,
                        latency_ms REAL,
                        error_message TEXT,
                        raw_response TEXT,
                        FOREIGN KEY (rule_execution_id) REFERENCES probe_rule_executions(id) ON DELETE CASCADE,
                        FOREIGN KEY (step_id) REFERENCES probe_rule_steps(id) ON DELETE CASCADE
                    )
                """,
            }

            for table_name, create_sql in rule_tables.items():
                result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"))
                if not result.fetchone():
                    conn.execute(text(create_sql))
                    index_sqls = {
                        "probe_rule_versions": [
                            "CREATE INDEX idx_rule_versions_rule_id ON probe_rule_versions(rule_id)"
                        ],
                        "probe_rule_steps": [
                            "CREATE INDEX idx_rule_steps_version_id ON probe_rule_steps(version_id)"
                        ],
                        "probe_rule_executions": [
                            "CREATE INDEX idx_rule_executions_target_id ON probe_rule_executions(target_id)",
                            "CREATE INDEX idx_rule_executions_version_id ON probe_rule_executions(version_id)",
                            "CREATE INDEX idx_rule_executions_timestamp ON probe_rule_executions(timestamp)",
                        ],
                        "probe_rule_step_executions": [
                            "CREATE INDEX idx_step_executions_rule_execution_id ON probe_rule_step_executions(rule_execution_id)",
                            "CREATE INDEX idx_step_executions_step_id ON probe_rule_step_executions(step_id)",
                            "CREATE INDEX idx_step_executions_timestamp ON probe_rule_step_executions(timestamp)",
                        ],
                    }
                    if table_name in index_sqls:
                        for idx_sql in index_sqls[table_name]:
                            conn.execute(text(idx_sql))
                    print(f"Created table {table_name}")

            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='dependencies'"))
            if not result.fetchone():
                conn.execute(text("""
                    CREATE TABLE dependencies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        upstream_id INTEGER NOT NULL,
                        downstream_id INTEGER NOT NULL,
                        description VARCHAR(255),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (upstream_id) REFERENCES probe_targets(id) ON DELETE CASCADE,
                        FOREIGN KEY (downstream_id) REFERENCES probe_targets(id) ON DELETE CASCADE
                    )
                """))
                conn.execute(text("CREATE INDEX idx_dependencies_upstream ON dependencies(upstream_id)"))
                conn.execute(text("CREATE INDEX idx_dependencies_downstream ON dependencies(downstream_id)"))
                print("Created dependencies table")

            snapshot_tables = {
                "snapshots": """
                    CREATE TABLE snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(255) NOT NULL,
                        description VARCHAR(1024),
                        start_time DATETIME NOT NULL,
                        end_time DATETIME NOT NULL,
                        target_count INTEGER DEFAULT 0,
                        data_point_count INTEGER DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                "snapshot_data": """
                    CREATE TABLE snapshot_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        snapshot_id INTEGER NOT NULL,
                        target_id INTEGER NOT NULL,
                        target_name VARCHAR(255) NOT NULL,
                        timestamp DATETIME NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        latency_ms REAL,
                        success INTEGER NOT NULL,
                        consecutive_failures INTEGER DEFAULT 0,
                        consecutive_successes INTEGER DEFAULT 0,
                        error_message TEXT,
                        FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
                    )
                """,
                "snapshot_alerts": """
                    CREATE TABLE snapshot_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        snapshot_id INTEGER NOT NULL,
                        target_id INTEGER NOT NULL,
                        target_name VARCHAR(255) NOT NULL,
                        timestamp DATETIME NOT NULL,
                        from_status VARCHAR(20) NOT NULL,
                        to_status VARCHAR(20) NOT NULL,
                        FOREIGN KEY (snapshot_id) REFERENCES snapshots(id) ON DELETE CASCADE
                    )
                """,
            }

            for table_name, create_sql in snapshot_tables.items():
                result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"))
                if not result.fetchone():
                    conn.execute(text(create_sql))
                    index_sqls = {
                        "snapshots": [
                            "CREATE INDEX idx_snapshots_start_time ON snapshots(start_time)",
                            "CREATE INDEX idx_snapshots_end_time ON snapshots(end_time)",
                            "CREATE INDEX idx_snapshots_created_at ON snapshots(created_at)",
                        ],
                        "snapshot_data": [
                            "CREATE INDEX idx_snapshot_data_snapshot_id ON snapshot_data(snapshot_id)",
                            "CREATE INDEX idx_snapshot_data_target_id ON snapshot_data(target_id)",
                            "CREATE INDEX idx_snapshot_data_timestamp ON snapshot_data(timestamp)",
                        ],
                        "snapshot_alerts": [
                            "CREATE INDEX idx_snapshot_alerts_snapshot_id ON snapshot_alerts(snapshot_id)",
                            "CREATE INDEX idx_snapshot_alerts_target_id ON snapshot_alerts(target_id)",
                            "CREATE INDEX idx_snapshot_alerts_timestamp ON snapshot_alerts(timestamp)",
                        ],
                    }
                    if table_name in index_sqls:
                        for idx_sql in index_sqls[table_name]:
                            conn.execute(text(idx_sql))
                    print(f"Created table {table_name}")

            observer_tables = {
                "observation_points": """
                    CREATE TABLE observation_points (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(255) NOT NULL,
                        region VARCHAR(100) NOT NULL,
                        status VARCHAR(20) DEFAULT 'online',
                        last_heartbeat DATETIME DEFAULT CURRENT_TIMESTAMP,
                        description VARCHAR(512),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                "target_observer_bindings": """
                    CREATE TABLE target_observer_bindings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        target_id INTEGER NOT NULL,
                        observer_id INTEGER NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (target_id) REFERENCES probe_targets(id) ON DELETE CASCADE,
                        FOREIGN KEY (observer_id) REFERENCES observation_points(id) ON DELETE CASCADE
                    )
                """,
                "observer_probe_results": """
                    CREATE TABLE observer_probe_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        target_id INTEGER NOT NULL,
                        observer_id INTEGER NOT NULL,
                        round_id VARCHAR(64) NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        success INTEGER NOT NULL,
                        latency_ms REAL,
                        error_message TEXT,
                        FOREIGN KEY (target_id) REFERENCES probe_targets(id) ON DELETE CASCADE,
                        FOREIGN KEY (observer_id) REFERENCES observation_points(id) ON DELETE CASCADE
                    )
                """,
            }

            for table_name, create_sql in observer_tables.items():
                result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"))
                if not result.fetchone():
                    conn.execute(text(create_sql))
                    index_sqls = {
                        "target_observer_bindings": [
                            "CREATE INDEX idx_tob_target_id ON target_observer_bindings(target_id)",
                            "CREATE INDEX idx_tob_observer_id ON target_observer_bindings(observer_id)",
                        ],
                        "observer_probe_results": [
                            "CREATE INDEX idx_opr_target_id ON observer_probe_results(target_id)",
                            "CREATE INDEX idx_opr_observer_id ON observer_probe_results(observer_id)",
                            "CREATE INDEX idx_opr_round_id ON observer_probe_results(round_id)",
                            "CREATE INDEX idx_opr_timestamp ON observer_probe_results(timestamp)",
                        ],
                    }
                    if table_name in index_sqls:
                        for idx_sql in index_sqls[table_name]:
                            conn.execute(text(idx_sql))
                    print(f"Created table {table_name}")

            change_tables = {
                "changes": """
                    CREATE TABLE changes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(255) NOT NULL,
                        description VARCHAR(1024),
                        planned_time DATETIME NOT NULL,
                        status VARCHAR(20) DEFAULT 'pending',
                        start_time DATETIME,
                        end_time DATETIME,
                        baseline_snapshot_id INTEGER,
                        result_snapshot_id INTEGER,
                        conclusion VARCHAR(20),
                        conclusion_reason VARCHAR(1024),
                        notes VARCHAR(2048),
                        created_by VARCHAR(100),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (baseline_snapshot_id) REFERENCES snapshots(id),
                        FOREIGN KEY (result_snapshot_id) REFERENCES snapshots(id)
                    )
                """,
                "change_targets": """
                    CREATE TABLE change_targets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        change_id INTEGER NOT NULL,
                        target_id INTEGER NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (change_id) REFERENCES changes(id) ON DELETE CASCADE,
                        FOREIGN KEY (target_id) REFERENCES probe_targets(id) ON DELETE CASCADE
                    )
                """,
                "change_events": """
                    CREATE TABLE change_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        change_id INTEGER NOT NULL,
                        event_type VARCHAR(50) NOT NULL,
                        message VARCHAR(1024) NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        data TEXT,
                        FOREIGN KEY (change_id) REFERENCES changes(id) ON DELETE CASCADE
                    )
                """,
            }

            for table_name, create_sql in change_tables.items():
                result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"))
                if not result.fetchone():
                    conn.execute(text(create_sql))
                    index_sqls = {
                        "changes": [
                            "CREATE INDEX idx_changes_status ON changes(status)",
                            "CREATE INDEX idx_changes_planned_time ON changes(planned_time)",
                            "CREATE INDEX idx_changes_start_time ON changes(start_time)",
                            "CREATE INDEX idx_changes_end_time ON changes(end_time)",
                            "CREATE INDEX idx_changes_created_at ON changes(created_at)",
                        ],
                        "change_targets": [
                            "CREATE INDEX idx_ct_change_id ON change_targets(change_id)",
                            "CREATE INDEX idx_ct_target_id ON change_targets(target_id)",
                        ],
                        "change_events": [
                            "CREATE INDEX idx_ce_change_id ON change_events(change_id)",
                            "CREATE INDEX idx_ce_timestamp ON change_events(timestamp)",
                            "CREATE INDEX idx_ce_event_type ON change_events(event_type)",
                        ],
                    }
                    if table_name in index_sqls:
                        for idx_sql in index_sqls[table_name]:
                            conn.execute(text(idx_sql))
                    print(f"Created table {table_name}")

            slo_tables = {
                "slo_targets": """
                    CREATE TABLE slo_targets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(255) NOT NULL,
                        description VARCHAR(1024),
                        target_id INTEGER,
                        group_id INTEGER,
                        slo_type VARCHAR(30) NOT NULL DEFAULT 'availability',
                        slo_target REAL NOT NULL DEFAULT 99.9,
                        latency_threshold_ms REAL,
                        window_days INTEGER NOT NULL DEFAULT 30,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (target_id) REFERENCES probe_targets(id) ON DELETE SET NULL,
                        FOREIGN KEY (group_id) REFERENCES probe_groups(id) ON DELETE SET NULL
                    )
                """,
                "slo_budget_snapshots": """
                    CREATE TABLE slo_budget_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        slo_id INTEGER NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        total_budget REAL NOT NULL,
                        budget_consumed REAL NOT NULL,
                        budget_remaining REAL NOT NULL,
                        current_value REAL NOT NULL,
                        service_fault REAL DEFAULT 0,
                        regional_anomaly REAL DEFAULT 0,
                        dependency_cascade REAL DEFAULT 0,
                        change_induced REAL DEFAULT 0,
                        FOREIGN KEY (slo_id) REFERENCES slo_targets(id) ON DELETE CASCADE
                    )
                """,
            }

            for table_name, create_sql in slo_tables.items():
                result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"))
                if not result.fetchone():
                    conn.execute(text(create_sql))
                    index_sqls = {
                        "slo_targets": [
                            "CREATE INDEX idx_slo_targets_target_id ON slo_targets(target_id)",
                            "CREATE INDEX idx_slo_targets_group_id ON slo_targets(group_id)",
                        ],
                        "slo_budget_snapshots": [
                            "CREATE INDEX idx_sbs_slo_id ON slo_budget_snapshots(slo_id)",
                            "CREATE INDEX idx_sbs_timestamp ON slo_budget_snapshots(timestamp)",
                        ],
                    }
                    if table_name in index_sqls:
                        for idx_sql in index_sqls[table_name]:
                            conn.execute(text(idx_sql))
                    print(f"Created table {table_name}")

            incident_tables = {
                "incidents": """
                    CREATE TABLE incidents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title VARCHAR(512) NOT NULL,
                        description TEXT,
                        severity VARCHAR(20) DEFAULT 'warning',
                        status VARCHAR(30) DEFAULT 'active',
                        first_anomaly_at DATETIME NOT NULL,
                        last_anomaly_at DATETIME NOT NULL,
                        recovered_at DATETIME,
                        bleed_over_until DATETIME,
                        mitigated INTEGER DEFAULT 0,
                        mitigated_at DATETIME,
                        owner VARCHAR(100),
                        acknowledged INTEGER DEFAULT 0,
                        acknowledged_at DATETIME,
                        acknowledged_by VARCHAR(100),
                        needs_review INTEGER DEFAULT 0,
                        review_notes TEXT,
                        parent_incident_id INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (parent_incident_id) REFERENCES incidents(id)
                    )
                """,
                "incident_targets": """
                    CREATE TABLE incident_targets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        incident_id INTEGER NOT NULL,
                        target_id INTEGER NOT NULL,
                        role VARCHAR(30) DEFAULT 'affected',
                        first_alert_at DATETIME,
                        last_alert_at DATETIME,
                        max_severity VARCHAR(20) DEFAULT 'warning',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
                        FOREIGN KEY (target_id) REFERENCES probe_targets(id) ON DELETE CASCADE
                    )
                """,
                "incident_alerts": """
                    CREATE TABLE incident_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        incident_id INTEGER NOT NULL,
                        alert_id INTEGER NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
                        FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE
                    )
                """,
                "incident_timeline": """
                    CREATE TABLE incident_timeline (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        incident_id INTEGER NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        event_type VARCHAR(50) NOT NULL,
                        title VARCHAR(512) NOT NULL,
                        description TEXT,
                        severity VARCHAR(20),
                        extra_data TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE
                    )
                """,
                "incident_notes": """
                    CREATE TABLE incident_notes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        incident_id INTEGER NOT NULL,
                        author VARCHAR(100) NOT NULL,
                        content TEXT NOT NULL,
                        action_type VARCHAR(30) DEFAULT 'note',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE
                    )
                """,
            }

            for table_name, create_sql in incident_tables.items():
                result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"))
                if not result.fetchone():
                    conn.execute(text(create_sql))
                    index_sqls = {
                        "incidents": [
                            "CREATE INDEX idx_incidents_status ON incidents(status)",
                            "CREATE INDEX idx_incidents_first_anomaly ON incidents(first_anomaly_at)",
                            "CREATE INDEX idx_incidents_recovered ON incidents(recovered_at)",
                            "CREATE INDEX idx_incidents_created ON incidents(created_at)",
                        ],
                        "incident_targets": [
                            "CREATE INDEX idx_it_incident_id ON incident_targets(incident_id)",
                            "CREATE INDEX idx_it_target_id ON incident_targets(target_id)",
                        ],
                        "incident_alerts": [
                            "CREATE INDEX idx_ia_incident_id ON incident_alerts(incident_id)",
                            "CREATE INDEX idx_ia_alert_id ON incident_alerts(alert_id)",
                        ],
                        "incident_timeline": [
                            "CREATE INDEX idx_itl_incident_id ON incident_timeline(incident_id)",
                            "CREATE INDEX idx_itl_timestamp ON incident_timeline(timestamp)",
                        ],
                        "incident_notes": [
                            "CREATE INDEX idx_in_incident_id ON incident_notes(incident_id)",
                            "CREATE INDEX idx_in_created_at ON incident_notes(created_at)",
                        ],
                    }
                    if table_name in index_sqls:
                        for idx_sql in index_sqls[table_name]:
                            conn.execute(text(idx_sql))
                    print(f"Created table {table_name}")

            discovery_tables = {
                "registry_sources": """
                    CREATE TABLE registry_sources (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(255) NOT NULL,
                        url VARCHAR(1024) NOT NULL,
                        pull_interval INTEGER NOT NULL DEFAULT 60,
                        default_group_id INTEGER,
                        default_type VARCHAR(10) NOT NULL DEFAULT 'http',
                        default_interval INTEGER NOT NULL DEFAULT 30,
                        default_timeout INTEGER NOT NULL DEFAULT 5,
                        deprecate_after_hours INTEGER NOT NULL DEFAULT 24,
                        enabled INTEGER DEFAULT 1,
                        last_sync_at DATETIME,
                        last_sync_status VARCHAR(20),
                        headers TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (default_group_id) REFERENCES probe_groups(id) ON DELETE SET NULL
                    )
                """,
                "sync_events": """
                    CREATE TABLE sync_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_id INTEGER NOT NULL,
                        triggered_by VARCHAR(20) NOT NULL DEFAULT 'auto',
                        status VARCHAR(20) NOT NULL DEFAULT 'running',
                        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        finished_at DATETIME,
                        discovered_count INTEGER DEFAULT 0,
                        new_count INTEGER DEFAULT 0,
                        deprecated_count INTEGER DEFAULT 0,
                        failed_count INTEGER DEFAULT 0,
                        unchanged_count INTEGER DEFAULT 0,
                        error_message TEXT,
                        raw_service_count INTEGER DEFAULT 0,
                        FOREIGN KEY (source_id) REFERENCES registry_sources(id) ON DELETE CASCADE
                    )
                """,
                "sync_event_details": """
                    CREATE TABLE sync_event_details (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_id INTEGER NOT NULL,
                        target_id INTEGER,
                        service_name VARCHAR(255) NOT NULL,
                        service_address VARCHAR(512) NOT NULL,
                        action VARCHAR(20) NOT NULL,
                        detail TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (event_id) REFERENCES sync_events(id) ON DELETE CASCADE,
                        FOREIGN KEY (target_id) REFERENCES probe_targets(id) ON DELETE SET NULL
                    )
                """,
            }

            for table_name, create_sql in discovery_tables.items():
                result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"))
                if not result.fetchone():
                    conn.execute(text(create_sql))
                    index_sqls = {
                        "registry_sources": [
                            "CREATE INDEX idx_rs_default_group_id ON registry_sources(default_group_id)",
                        ],
                        "sync_events": [
                            "CREATE INDEX idx_se_source_id ON sync_events(source_id)",
                            "CREATE INDEX idx_se_started_at ON sync_events(started_at)",
                            "CREATE INDEX idx_se_status ON sync_events(status)",
                        ],
                        "sync_event_details": [
                            "CREATE INDEX idx_sed_event_id ON sync_event_details(event_id)",
                            "CREATE INDEX idx_sed_target_id ON sync_event_details(target_id)",
                            "CREATE INDEX idx_sed_action ON sync_event_details(action)",
                        ],
                    }
                    if table_name in index_sqls:
                        for idx_sql in index_sqls[table_name]:
                            conn.execute(text(idx_sql))
                    print(f"Created table {table_name}")

            result = conn.execute(text("PRAGMA table_info(probe_targets)"))
            columns = [row[1] for row in result.fetchall()]
            discovery_target_columns = [
                ("source_id", "INTEGER"),
                ("deprecated", "INTEGER DEFAULT 0"),
                ("deprecated_at", "DATETIME"),
                ("last_seen_at", "DATETIME"),
            ]
            for col_name, col_def in discovery_target_columns:
                if col_name not in columns:
                    conn.execute(text(f"ALTER TABLE probe_targets ADD COLUMN {col_name} {col_def}"))
                    print(f"Added column {col_name} to probe_targets")

            conn.execute(text("UPDATE probe_targets SET deprecated = 0 WHERE deprecated IS NULL"))
            conn.execute(text("UPDATE probe_targets SET source_id = NULL WHERE source_id IS NOT NULL AND source_id NOT IN (SELECT id FROM registry_sources)"))

            recording_tables = {
                "recording_sessions": """
                    CREATE TABLE recording_sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(255) NOT NULL,
                        description VARCHAR(1024),
                        tags TEXT,
                        status VARCHAR(20) DEFAULT 'recording',
                        started_at DATETIME NOT NULL,
                        ended_at DATETIME,
                        duration_seconds INTEGER DEFAULT 0,
                        recorded_count INTEGER DEFAULT 0,
                        target_count INTEGER DEFAULT 0,
                        filter_target_ids TEXT,
                        filter_group_ids TEXT,
                        created_by VARCHAR(100),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                "recording_events": """
                    CREATE TABLE recording_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER NOT NULL,
                        event_type VARCHAR(30) NOT NULL,
                        target_id INTEGER,
                        target_name VARCHAR(255),
                        relative_time_ms INTEGER NOT NULL,
                        sequence INTEGER NOT NULL,
                        payload TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES recording_sessions(id) ON DELETE CASCADE
                    )
                """,
                "playback_snapshots": """
                    CREATE TABLE playback_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER NOT NULL UNIQUE,
                        targets_snapshot TEXT NOT NULL,
                        alerts_snapshot TEXT NOT NULL,
                        incidents_snapshot TEXT NOT NULL,
                        groups_snapshot TEXT NOT NULL,
                        dependencies_snapshot TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES recording_sessions(id) ON DELETE CASCADE
                    )
                """,
            }

            for table_name, create_sql in recording_tables.items():
                result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"))
                if not result.fetchone():
                    conn.execute(text(create_sql))
                    index_sqls = {
                        "recording_sessions": [
                            "CREATE INDEX idx_recording_sessions_status ON recording_sessions(status)",
                            "CREATE INDEX idx_recording_sessions_started_at ON recording_sessions(started_at)",
                            "CREATE INDEX idx_recording_sessions_created_at ON recording_sessions(created_at)",
                        ],
                        "recording_events": [
                            "CREATE INDEX idx_recording_events_session_id ON recording_events(session_id)",
                            "CREATE INDEX idx_recording_events_event_type ON recording_events(event_type)",
                            "CREATE INDEX idx_recording_events_target_id ON recording_events(target_id)",
                            "CREATE INDEX idx_recording_events_relative_time ON recording_events(relative_time_ms)",
                        ],
                        "playback_snapshots": [
                            "CREATE INDEX idx_playback_snapshots_session_id ON playback_snapshots(session_id)",
                        ],
                    }
                    if table_name in index_sqls:
                        for idx_sql in index_sqls[table_name]:
                            conn.execute(text(idx_sql))
                    print(f"Created table {table_name}")

            maintenance_tables = {
                "maintenance_windows": """
                    CREATE TABLE maintenance_windows (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        target_id INTEGER NOT NULL,
                        group_id INTEGER,
                        title VARCHAR(255) NOT NULL,
                        description TEXT,
                        start_time DATETIME NOT NULL,
                        end_time DATETIME NOT NULL,
                        reason VARCHAR(255),
                        owner VARCHAR(100),
                        status VARCHAR(20) DEFAULT 'scheduled',
                        is_cancelled INTEGER DEFAULT 0,
                        cancelled_at DATETIME,
                        cancelled_reason VARCHAR(512),
                        actual_start_time DATETIME,
                        actual_end_time DATETIME,
                        timeout_alert_sent INTEGER DEFAULT 0,
                        extension_reason TEXT,
                        created_by VARCHAR(100),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (target_id) REFERENCES probe_targets(id) ON DELETE CASCADE,
                        FOREIGN KEY (group_id) REFERENCES probe_groups(id) ON DELETE SET NULL
                    )
                """,
                "maintenance_window_events": """
                    CREATE TABLE maintenance_window_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        window_id INTEGER NOT NULL,
                        event_type VARCHAR(30) NOT NULL,
                        message VARCHAR(512) NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        extra_data TEXT,
                        FOREIGN KEY (window_id) REFERENCES maintenance_windows(id) ON DELETE CASCADE
                    )
                """,
            }

            for table_name, create_sql in maintenance_tables.items():
                result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"))
                if not result.fetchone():
                    conn.execute(text(create_sql))
                    index_sqls = {
                        "maintenance_windows": [
                            "CREATE INDEX idx_mw_target_id ON maintenance_windows(target_id)",
                            "CREATE INDEX idx_mw_group_id ON maintenance_windows(group_id)",
                            "CREATE INDEX idx_mw_start_time ON maintenance_windows(start_time)",
                            "CREATE INDEX idx_mw_end_time ON maintenance_windows(end_time)",
                            "CREATE INDEX idx_mw_status ON maintenance_windows(status)",
                            "CREATE INDEX idx_mw_created_at ON maintenance_windows(created_at)",
                        ],
                        "maintenance_window_events": [
                            "CREATE INDEX idx_mwe_window_id ON maintenance_window_events(window_id)",
                            "CREATE INDEX idx_mwe_timestamp ON maintenance_window_events(timestamp)",
                            "CREATE INDEX idx_mwe_event_type ON maintenance_window_events(event_type)",
                        ],
                    }
                    if table_name in index_sqls:
                        for idx_sql in index_sqls[table_name]:
                            conn.execute(text(idx_sql))
                    print(f"Created table {table_name}")

            conn.commit()
        except Exception as e:
            print(f"Migration error: {e}")


_create_tables()
_migrate_database()

app = FastAPI(title="Probe Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    import asyncio
    import os
    loop = asyncio.get_running_loop()
    probe_engine.set_loop(loop)
    manager.set_loop(loop)
    observer_engine.set_loop(loop)
    recording_engine.set_loop(loop)
    playback_engine.set_loop(loop)
    maintenance_engine.set_loop(loop)

    if os.getenv("RESET_DEMO_DATA", "false").lower() == "true":
        db_path = "./data/probes.db"
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
                print("Demo database reset - removed old probes.db")
            except Exception as e:
                print(f"Failed to remove old database: {e}")

    _create_tables()
    _migrate_database()

    _init_demo_data()
    _init_demo_rules()
    _init_demo_observers()
    _init_demo_changes()
    _init_demo_slo()
    _init_demo_incidents()
    incident_engine.attach_callbacks()
    maintenance_engine.register_status_callback(lambda data: manager.broadcast_maintenance_update())
    await observer_engine.start()
    await probe_engine.start()
    await sync_engine.start()
    await maintenance_engine.start()


@app.on_event("shutdown")
async def shutdown_event():
    await observer_engine.stop()
    await probe_engine.stop()
    await sync_engine.stop()
    await maintenance_engine.stop()


def _init_demo_slo():
    db = next(get_db())
    try:
        slo_count = db.query(SLOTarget).count()
        if slo_count > 0:
            return

        now = datetime.utcnow()
        target_healthy = db.query(ProbeTarget).filter(ProbeTarget.name.like("%健康%")).first()
        target_degraded = db.query(ProbeTarget).filter(ProbeTarget.name.like("%间歇%")).first()
        target_down = db.query(ProbeTarget).filter(ProbeTarget.name.like("%不可达%")).first()
        group_prod = db.query(ProbeGroup).filter(ProbeGroup.name.like("%生产%")).first()
        group_test = db.query(ProbeGroup).filter(ProbeGroup.name.like("%测试%")).first()

        slo1 = SLOTarget(
            name="生产核心服务可用性",
            description="生产环境核心业务线月度可用性SLO",
            target_id=target_healthy.id if target_healthy else None,
            group_id=group_prod.id if group_prod else None,
            slo_type="availability",
            slo_target=99.95,
            latency_threshold_ms=200,
            window_days=30,
            created_at=now,
            updated_at=now,
        )
        db.add(slo1)

        slo2 = SLOTarget(
            name="间歇故障服务可用性",
            description="间歇故障服务的SLO - 预算快速燃尽",
            target_id=target_degraded.id if target_degraded else None,
            slo_type="availability",
            slo_target=99.9,
            latency_threshold_ms=500,
            window_days=30,
            created_at=now,
            updated_at=now,
        )
        db.add(slo2)

        slo3 = SLOTarget(
            name="不可达服务可用性",
            description="完全不可达服务的SLO - 预算即将耗尽",
            target_id=target_down.id if target_down else None,
            group_id=group_test.id if group_test else None,
            slo_type="availability",
            slo_target=99.5,
            latency_threshold_ms=1000,
            window_days=30,
            created_at=now,
            updated_at=now,
        )
        db.add(slo3)
        db.flush()

        scenarios = {
            slo1.id: {"total_budget": 0.05, "start_pct": 0.02, "end_pct": 0.12,
                      "svc": 0.8, "reg": 0.1, "dep": 0.05, "chg": 0.05},
            slo2.id: {"total_budget": 0.1, "start_pct": 0.15, "end_pct": 0.65,
                      "svc": 0.3, "reg": 0.4, "dep": 0.2, "chg": 0.1},
            slo3.id: {"total_budget": 0.5, "start_pct": 0.50, "end_pct": 0.92,
                      "svc": 0.35, "reg": 0.1, "dep": 0.35, "chg": 0.2},
        }

        num_snapshots = 24
        for slo in [slo1, slo2, slo3]:
            cfg = scenarios[slo.id]
            tb = cfg["total_budget"]
            for i in range(num_snapshots):
                snap_time = now - timedelta(hours=(num_snapshots - i))
                progress = i / max(num_snapshots - 1, 1)
                consumed_pct = cfg["start_pct"] + (cfg["end_pct"] - cfg["start_pct"]) * progress
                budget_consumed = round(tb * consumed_pct, 6)
                budget_remaining = round(tb - budget_consumed, 6)
                current_value = round(100.0 - budget_consumed, 4)
                budget_remaining_pct = round((budget_remaining / tb) * 100, 1) if tb > 0 else 100

                snap = SLOBudgetSnapshot(
                    slo_id=slo.id,
                    timestamp=snap_time,
                    total_budget=round(tb, 4),
                    budget_consumed=budget_consumed,
                    budget_remaining=budget_remaining,
                    current_value=current_value,
                    service_fault=round(budget_consumed * cfg["svc"], 4),
                    regional_anomaly=round(budget_consumed * cfg["reg"], 4),
                    dependency_cascade=round(budget_consumed * cfg["dep"], 4),
                    change_induced=round(budget_consumed * cfg["chg"], 4),
                )
                db.add(snap)

        db.commit()
        print("Demo SLO data initialized")
    except Exception as e:
        print(f"Demo SLO init error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


class IncidentEngine:
    def __init__(self):
        self._alert_callback = None
        self._status_callback = None
        self.bleed_over_minutes = 30

    def attach_callbacks(self):
        probe_engine.register_alert_callback(self._on_new_alert)
        probe_engine.register_status_callback(self._on_status_update)

    def _on_new_alert(self, data: dict):
        db = next(get_db())
        try:
            alert_id = data.get("alert", {}).get("id")
            if not alert_id:
                return
            alert = db.query(Alert).filter(Alert.id == alert_id).first()
            if alert:
                self._process_alert(db, alert)
                db.commit()
                manager.broadcast_incidents_update()
        except Exception as e:
            print(f"Incident engine alert processing error: {e}")
            db.rollback()
        finally:
            db.close()

    def _on_status_update(self, data: dict):
        db = next(get_db())
        try:
            target_id = data.get("target", {}).get("id")
            new_status = data.get("target", {}).get("status")
            if not target_id or new_status != "healthy":
                return
            self._check_target_recovery(db, target_id)
            db.commit()
            manager.broadcast_incidents_update()
        except Exception as e:
            print(f"Incident engine status update error: {e}")
            db.rollback()
        finally:
            db.close()

    def _find_or_create_incident(self, db: Session, alert: Alert) -> Incident:
        now = datetime.utcnow()
        related_target_ids = self._get_related_target_ids(db, alert.target_id)

        active_incidents = db.query(Incident).filter(
            Incident.status.in_(["active", "recovering"])
        ).all()

        for incident in active_incidents:
            incident_target_ids = [it.target_id for it in incident.targets]
            overlap = set(related_target_ids) & set(incident_target_ids)
            if overlap:
                if incident.bleed_over_until and incident.bleed_over_until >= now:
                    incident.status = "active"
                    incident.recovered_at = None
                    self._add_timeline_event(db, incident.id, "status_change",
                                              "故障复发，重新进入处置状态",
                                              f"目标 {alert.target.name if alert.target else alert.target_id} 在恢复观察期内再次出现异常",
                                              "critical")
                    return incident
                if incident.status == "active":
                    return incident

        severity = "critical" if alert.to_status == "down" else "warning"
        target_name = alert.target.name if alert.target else f"Target-{alert.target_id}"

        incident = Incident(
            title=f"{target_name} 状态异常: {alert.from_status} → {alert.to_status}",
            description=f"自动生成的故障事件，由告警触发",
            severity=severity,
            status="active",
            first_anomaly_at=alert.timestamp,
            last_anomaly_at=alert.timestamp,
            mitigated=False,
            acknowledged=False,
            needs_review=False,
        )
        db.add(incident)
        db.flush()

        self._add_timeline_event(db, incident.id, "alert_triggered",
                                  "首个异常告警触发",
                                  f"{target_name}: {alert.from_status} → {alert.to_status}",
                                  severity)
        return incident

    def _get_related_target_ids(self, db: Session, target_id: int) -> Set[int]:
        related = {target_id}
        downstream = _get_downstream_targets(db, target_id)
        upstream = _get_upstream_targets(db, target_id)
        for t in downstream:
            related.add(t.id)
        for t in upstream:
            related.add(t.id)
        return related

    def _process_alert(self, db: Session, alert: Alert):
        existing = db.query(IncidentAlert).filter(IncidentAlert.alert_id == alert.id).first()
        if existing:
            return

        incident = self._find_or_create_incident(db, alert)

        db.add(IncidentAlert(
            incident_id=incident.id,
            alert_id=alert.id,
        ))

        severity = "critical" if alert.to_status == "down" else "warning"

        it = db.query(IncidentTarget).filter(
            IncidentTarget.incident_id == incident.id,
            IncidentTarget.target_id == alert.target_id
        ).first()

        if it:
            it.last_alert_at = alert.timestamp
            if severity == "critical":
                it.max_severity = "critical"
        else:
            db.add(IncidentTarget(
                incident_id=incident.id,
                target_id=alert.target_id,
                role="affected",
                first_alert_at=alert.timestamp,
                last_alert_at=alert.timestamp,
                max_severity=severity,
            ))

        if alert.timestamp < incident.first_anomaly_at:
            incident.first_anomaly_at = alert.timestamp
        if alert.timestamp > incident.last_anomaly_at:
            incident.last_anomaly_at = alert.timestamp

        existing_severity_order = {"warning": 1, "critical": 2}
        if existing_severity_order.get(severity, 0) > existing_severity_order.get(incident.severity, 0):
            incident.severity = severity

        target_name = alert.target.name if alert.target else f"Target-{alert.target_id}"
        self._add_timeline_event(db, incident.id, "alert",
                                  f"告警: {target_name}",
                                  f"{alert.from_status} → {alert.to_status}",
                                  severity)

    def _check_target_recovery(self, db: Session, target_id: int):
        now = datetime.utcnow()
        incident_targets = db.query(IncidentTarget).filter(
            IncidentTarget.target_id == target_id
        ).all()

        for it in incident_targets:
            incident = db.query(Incident).filter(Incident.id == it.incident_id).first()
            if not incident or incident.status not in ["active", "recovering"]:
                continue

            all_healthy = True
            for sit in incident.targets:
                t = db.query(ProbeTarget).filter(ProbeTarget.id == sit.target_id).first()
                if t and t.status not in ["healthy", "paused"]:
                    all_healthy = False
                    break

            if all_healthy:
                if incident.status == "active":
                    incident.status = "recovering"
                    incident.bleed_over_until = now + timedelta(minutes=self.bleed_over_minutes)
                    incident.recovered_at = now
                    target_names = ", ".join([
                        sit.target.name if sit.target else f"Target-{sit.target_id}"
                        for sit in incident.targets
                    ])
                    self._add_timeline_event(db, incident.id, "status_change",
                                              "所有目标恢复健康",
                                              f"受影响目标已全部恢复: {target_names}，进入 {self.bleed_over_minutes} 分钟观察期",
                                              "info")
            elif incident.status == "recovering":
                incident.status = "active"
                incident.recovered_at = None
                incident.bleed_over_until = None

    def _add_timeline_event(self, db: Session, incident_id: int, event_type: str,
                            title: str, description: str = None, severity: str = None,
                            extra_data: dict = None):
        db.add(IncidentTimeline(
            incident_id=incident_id,
            event_type=event_type,
            title=title,
            description=description,
            severity=severity,
            extra_data=extra_data,
        ))


incident_engine = IncidentEngine()


def _incident_to_response(incident: Incident, db: Session, include_details: bool = False) -> dict:
    now = datetime.utcnow()
    target_infos = []
    for it in incident.targets:
        target = db.query(ProbeTarget).options(joinedload(ProbeTarget.group)).filter(
            ProbeTarget.id == it.target_id
        ).first()
        target_infos.append({
            "target_id": it.target_id,
            "target_name": target.name if target else f"Target-{it.target_id}",
            "target_status": target.status if target else None,
            "group_name": target.group.name if target and target.group else None,
            "role": it.role,
            "first_alert_at": it.first_alert_at,
            "last_alert_at": it.last_alert_at,
            "max_severity": it.max_severity,
        })

    alert_infos = []
    for ia in incident.alerts:
        alert = ia.alert
        alert_infos.append({
            "alert_id": alert.id,
            "target_id": alert.target_id,
            "target_name": alert.target.name if alert.target else None,
            "timestamp": alert.timestamp,
            "from_status": alert.from_status,
            "to_status": alert.to_status,
        })

    timeline_events = []
    if include_details:
        for te in incident.timeline:
            timeline_events.append({
                "id": te.id,
                "timestamp": te.timestamp,
                "event_type": te.event_type,
                "title": te.title,
                "description": te.description,
                "severity": te.severity,
                "extra_data": te.extra_data,
            })

    notes = []
    if include_details:
        for note in incident.notes:
            notes.append({
                "id": note.id,
                "author": note.author,
                "content": note.content,
                "action_type": note.action_type,
                "created_at": note.created_at,
            })

    duration = None
    if incident.status in ["recovering", "resolved"] and incident.recovered_at:
        duration = int((incident.recovered_at - incident.first_anomaly_at).total_seconds())
    elif incident.status == "active":
        duration = int((now - incident.first_anomaly_at).total_seconds())

    upstream_deps = []
    downstream_deps = []
    if include_details:
        target_ids = [it.target_id for it in incident.targets]
        visited_up = set()
        visited_down = set()
        for tid in target_ids:
            ups = _get_upstream_targets(db, tid)
            for u in ups:
                if u.id not in visited_up and u.id not in target_ids:
                    visited_up.add(u.id)
                    upstream_deps.append({
                        "target_id": u.id,
                        "target_name": u.name,
                        "status": u.status,
                        "direction": "upstream",
                        "depth": 1,
                    })
            downs = _get_downstream_targets(db, tid)
            for d in downs:
                if d.id not in visited_down and d.id not in target_ids:
                    visited_down.add(d.id)
                    downstream_deps.append({
                        "target_id": d.id,
                        "target_name": d.name,
                        "status": d.status,
                        "direction": "downstream",
                        "depth": 1,
                    })

    active_changes = []
    if include_details:
        target_ids = [it.target_id for it in incident.targets]
        changes = db.query(Change).filter(
            Change.status.in_(["pending", "running"])
        ).options(joinedload(Change.targets)).all()
        for c in changes:
            affected = any(ct.target_id in target_ids for ct in c.targets)
            if affected or (c.start_time and c.start_time >= incident.first_anomaly_at - timedelta(hours=1)):
                active_changes.append({
                    "change_id": c.id,
                    "name": c.name,
                    "status": c.status,
                    "start_time": c.start_time,
                    "planned_time": c.planned_time,
                    "created_by": c.created_by,
                })

    region_divergence = []
    if include_details and hasattr(observer_engine, 'get_target_region_divergence'):
        try:
            for it in incident.targets:
                div = observer_engine.get_target_region_divergence(it.target_id)
                if div:
                    region_divergence.append(div)
        except Exception as e:
            print(f"Error getting region divergence: {e}")

    slo_risks = []
    if include_details:
        target_ids = [it.target_id for it in incident.targets]
        slos = db.query(SLOTarget).all()
        for slo in slos:
            related = False
            if slo.target_id and slo.target_id in target_ids:
                related = True
            if slo.group_id:
                for tid in target_ids:
                    t = db.query(ProbeTarget).filter(ProbeTarget.id == tid).first()
                    if t and t.group_id == slo.group_id:
                        related = True
                        break
            if related:
                budget = _calculate_budget_for_slo(slo, db)
                slo_risks.append({
                    "slo_id": slo.id,
                    "slo_name": slo.name,
                    "budget_remaining_pct": budget["budget_remaining_pct"],
                    "burn_rate": budget["burn_rate"],
                    "status": budget["status"],
                    "hours_to_breach": None,
                })

    return {
        "id": incident.id,
        "title": incident.title,
        "description": incident.description,
        "severity": incident.severity,
        "status": incident.status,
        "first_anomaly_at": incident.first_anomaly_at,
        "last_anomaly_at": incident.last_anomaly_at,
        "recovered_at": incident.recovered_at,
        "bleed_over_until": incident.bleed_over_until,
        "mitigated": incident.mitigated,
        "mitigated_at": incident.mitigated_at,
        "owner": incident.owner,
        "acknowledged": incident.acknowledged,
        "acknowledged_at": incident.acknowledged_at,
        "acknowledged_by": incident.acknowledged_by,
        "needs_review": incident.needs_review,
        "review_notes": incident.review_notes,
        "parent_incident_id": incident.parent_incident_id,
        "created_at": incident.created_at,
        "updated_at": incident.updated_at,
        "targets": target_infos,
        "alerts": alert_infos,
        "timeline": timeline_events,
        "notes": notes,
        "target_count": len(target_infos),
        "alert_count": len(alert_infos),
        "duration_seconds": duration,
        "upstream_dependencies": upstream_deps,
        "downstream_dependencies": downstream_deps,
        "active_changes": active_changes,
        "region_divergence": region_divergence,
        "slo_budget_risks": slo_risks,
    }


def _calculate_budget_for_slo(slo: SLOTarget, db: Session) -> dict:
    now = datetime.utcnow()
    window_start = now - timedelta(days=slo.window_days)

    related_target_ids = set()
    if slo.target_id:
        related_target_ids.add(slo.target_id)
    if slo.group_id:
        group_targets = db.query(ProbeTarget).filter(ProbeTarget.group_id == slo.group_id).all()
        for t in group_targets:
            related_target_ids.add(t.id)

    total_budget = 1.0 - (slo.slo_target / 100.0)

    if not related_target_ids:
        return {
            "total_budget": round(total_budget, 4),
            "budget_consumed": 0,
            "budget_remaining": round(total_budget, 4),
            "budget_remaining_pct": 100.0,
            "current_value": round(slo.slo_target, 4),
            "burn_rate": 0,
            "status": "healthy",
        }

    results = db.query(ProbeResult).filter(
        ProbeResult.target_id.in_(list(related_target_ids)),
        ProbeResult.timestamp >= window_start
    ).all()

    total_checks = len(results)
    failed_checks = sum(1 for r in results if not r.success)
    error_rate = failed_checks / total_checks if total_checks > 0 else 0

    budget_consumed = min(error_rate, total_budget) if total_budget > 0 else 0
    budget_remaining = max(total_budget - budget_consumed, 0)
    budget_remaining_pct = (budget_remaining / total_budget * 100) if total_budget > 0 else 100
    current_value = 100.0 - (error_rate * 100)

    recent_results = db.query(ProbeResult).filter(
        ProbeResult.target_id.in_(list(related_target_ids)),
        ProbeResult.timestamp >= now - timedelta(hours=1)
    ).all()
    recent_total = len(recent_results)
    recent_failed = sum(1 for r in recent_results if not r.success)
    recent_error_rate = recent_failed / recent_total if recent_total > 0 else 0

    hourly_budget = total_budget / (slo.window_days * 24) if total_budget > 0 else 0
    burn_rate = (recent_error_rate / hourly_budget) if hourly_budget > 0 else 0

    if budget_remaining_pct <= 5 or burn_rate >= 10:
        status = "critical"
    elif budget_remaining_pct <= 20 or burn_rate >= 2:
        status = "warning"
    else:
        status = "healthy"

    return {
        "total_budget": round(total_budget, 4),
        "budget_consumed": round(budget_consumed, 6),
        "budget_remaining": round(budget_remaining, 6),
        "budget_remaining_pct": round(budget_remaining_pct, 1),
        "current_value": round(current_value, 4),
        "burn_rate": round(burn_rate, 2),
        "status": status,
    }


def _init_demo_incidents():
    db = next(get_db())
    try:
        incident_count = db.query(Incident).count()
        if incident_count > 0:
            return

        now = datetime.utcnow()
        degraded_target = db.query(ProbeTarget).filter(ProbeTarget.name.like("%间歇%")).first()
        down_target = db.query(ProbeTarget).filter(ProbeTarget.name.like("%不可达%")).first()
        healthy_target = db.query(ProbeTarget).filter(ProbeTarget.name.like("%健康%")).first()

        if not degraded_target or not down_target:
            return

        incident_active = Incident(
            title="核心服务降级告警 - 多地区观测分歧",
            description="间歇故障服务在华南地区观测点持续异常，其他地区正常，疑似区域性网络或节点问题",
            severity="warning",
            status="active",
            first_anomaly_at=now - timedelta(minutes=45),
            last_anomaly_at=now - timedelta(minutes=2),
            mitigated=False,
            acknowledged=True,
            acknowledged_at=now - timedelta(minutes=40),
            acknowledged_by="张三",
            owner="李四",
            needs_review=False,
            created_at=now - timedelta(minutes=45),
            updated_at=now,
        )
        db.add(incident_active)
        db.flush()

        db.add(IncidentTarget(
            incident_id=incident_active.id,
            target_id=degraded_target.id,
            role="source",
            first_alert_at=now - timedelta(minutes=45),
            last_alert_at=now - timedelta(minutes=5),
            max_severity="warning",
        ))
        db.flush()

        alerts_degraded = db.query(Alert).filter(Alert.target_id == degraded_target.id).all()
        for a in alerts_degraded:
            db.add(IncidentAlert(incident_id=incident_active.id, alert_id=a.id))

        timeline_active = [
            ("alert_triggered", "首个异常告警触发", "示例服务-间歇故障: healthy → degraded", "warning", now - timedelta(minutes=45)),
            ("status_change", "告警自动确认并分派", "系统自动确认，分派给值班工程师李四", "info", now - timedelta(minutes=42)),
            ("acknowledged", "张三手动接管", "值班人员张三确认告警并开始排查", "info", now - timedelta(minutes=40)),
            ("observation_divergence", "发现多地区观测分歧", "华北/华东/西南正常，华南地区持续异常，美西离线", "warning", now - timedelta(minutes=35)),
            ("investigation", "排查进展: 关联到变更窗口", "发现异常时间与变更守护中的配置发布窗口重合", "info", now - timedelta(minutes=25)),
            ("owner_transfer", "转交负责人", "转交李四处理，其为该服务Owner", "info", now - timedelta(minutes=15)),
            ("mitigation", "临时止血方案实施中", "正在将华南地区流量切转到备用集群", "info", now - timedelta(minutes=5)),
        ]
        for et, title, desc, sev, ts in timeline_active:
            db.add(IncidentTimeline(
                incident_id=incident_active.id,
                event_type=et,
                title=title,
                description=desc,
                severity=sev,
                timestamp=ts,
            ))

        notes_active = [
            ("张三", "初步怀疑是CDN回源问题，已联系网络组协助排查", "note", now - timedelta(minutes=38)),
            ("李四", "该服务昨天晚上有一次配置发布，需要对比快照", "note", now - timedelta(minutes=20)),
            ("李四", "SLO预算燃尽率目前2.3x，需要在12小时内解决", "note", now - timedelta(minutes=10)),
        ]
        for author, content, atype, ts in notes_active:
            db.add(IncidentNote(
                incident_id=incident_active.id,
                author=author,
                content=content,
                action_type=atype,
                created_at=ts,
            ))

        incident_recovered = Incident(
            title="测试环境服务不可达 - 已恢复待复盘",
            description="示例服务-不可达因上游依赖故障导致完全不可达，根因已定位并修复，需要召开复盘会",
            severity="critical",
            status="recovering",
            first_anomaly_at=now - timedelta(hours=2, minutes=30),
            last_anomaly_at=now - timedelta(hours=1, minutes=15),
            recovered_at=now - timedelta(hours=1),
            bleed_over_until=now - timedelta(minutes=30),
            mitigated=True,
            mitigated_at=now - timedelta(hours=1, minutes=45),
            acknowledged=True,
            acknowledged_at=now - timedelta(hours=2, minutes=20),
            acknowledged_by="王五",
            owner="赵六",
            needs_review=True,
            review_notes="需要复盘：1.上游依赖故障为什么没有提前预警 2.故障恢复时间是否符合SLA 3.是否需要增加降级开关",
            created_at=now - timedelta(hours=2, minutes=30),
            updated_at=now - timedelta(hours=1),
        )
        db.add(incident_recovered)
        db.flush()

        db.add(IncidentTarget(
            incident_id=incident_recovered.id,
            target_id=down_target.id,
            role="source",
            first_alert_at=now - timedelta(hours=2, minutes=30),
            last_alert_at=now - timedelta(hours=1, minutes=15),
            max_severity="critical",
        ))
        db.flush()

        alerts_down = db.query(Alert).filter(Alert.target_id == down_target.id).all()
        for a in alerts_down:
            db.add(IncidentAlert(incident_id=incident_recovered.id, alert_id=a.id))

        timeline_recovered = [
            ("alert_triggered", "服务状态降级", "示例服务-不可达: healthy → degraded", "warning", now - timedelta(hours=2, minutes=30)),
            ("alert_triggered", "服务完全不可达", "示例服务-不可达: degraded → down", "critical", now - timedelta(hours=2, minutes=15)),
            ("acknowledged", "王五确认告警", "确认是测试环境核心服务不可达", "info", now - timedelta(hours=2, minutes=20)),
            ("cascade_detected", "发现下游依赖受影响", "依赖拓扑检测到API网关和内部文档服务受到级联影响", "warning", now - timedelta(hours=2, minutes=10)),
            ("investigation", "根因定位: 上游数据库连接池耗尽", "通过日志排查发现上游数据库连接池在发布后被占满", "info", now - timedelta(hours=1, minutes=55)),
            ("mitigation", "实施止血: 重启数据库连接池", "通过运维平台重启数据库连接池服务", "info", now - timedelta(hours=1, minutes=45)),
            ("status_change", "服务开始恢复", "示例服务-不可达: down → degraded", "info", now - timedelta(hours=1, minutes=30)),
            ("status_change", "所有目标恢复健康", "受影响目标已全部恢复，进入 30 分钟观察期", "info", now - timedelta(hours=1)),
            ("observation_summary", "地区观测一致性检查", "所有在线观测点均确认服务恢复正常", "info", now - timedelta(hours=1)),
        ]
        for et, title, desc, sev, ts in timeline_recovered:
            db.add(IncidentTimeline(
                incident_id=incident_recovered.id,
                event_type=et,
                title=title,
                description=desc,
                severity=sev,
                timestamp=ts,
            ))

        notes_recovered = [
            ("王五", "测试环境数据库最近有版本升级，可能是连接池配置问题", "note", now - timedelta(hours=2, minutes=5)),
            ("赵六", "连接池最大连接数配置被改小了，发布时没注意到这个变更", "note", now - timedelta(hours=1, minutes=50)),
            ("赵六", "服务已恢复，观察期中，稍后创建复盘会议", "note", now - timedelta(hours=55)),
        ]
        for author, content, atype, ts in notes_recovered:
            db.add(IncidentNote(
                incident_id=incident_recovered.id,
                author=author,
                content=content,
                action_type=atype,
                created_at=ts,
            ))

        db.commit()
        print("Demo incidents initialized")
    except Exception as e:
        print(f"Demo incidents init error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def _init_demo_data():
    db = next(get_db())
    try:
        target_count = db.query(ProbeTarget).count()
        group_count = db.query(ProbeGroup).count()
        if target_count > 0 and group_count > 0:
            return

        now = datetime.utcnow()

        group1 = ProbeGroup(
            name="生产环境",
            description="核心业务线生产环境服务",
            color="#ef4444",
            degrade_threshold=3,
            down_threshold=8,
            success_threshold=3,
            adaptive_enabled=True,
            slow_interval=60,
            fast_interval=5,
            silent_start="02:00",
            silent_end="06:00"
        )
        db.add(group1)
        db.flush()

        group2 = ProbeGroup(
            name="测试环境",
            description="测试环境服务，容忍度较高",
            color="#22c55e",
            degrade_threshold=5,
            down_threshold=10,
            success_threshold=2,
            adaptive_enabled=False,
            slow_interval=120,
            fast_interval=10
        )
        db.add(group2)
        db.flush()

        group3 = ProbeGroup(
            name="内部工具",
            description="内部工具和第三方依赖",
            color="#3b82f6",
            degrade_threshold=2,
            down_threshold=5,
            success_threshold=3,
            adaptive_enabled=True,
            slow_interval=120,
            fast_interval=15,
            silent_start="01:00",
            silent_end="05:00"
        )
        db.add(group3)
        db.flush()

        target1 = ProbeTarget(
            name="示例服务-健康",
            group_id=group1.id,
            type="http",
            address="https://httpbin.org/status/200",
            interval=10,
            timeout=5,
            expected_status="200",
            status="healthy",
            consecutive_successes=10,
            consecutive_failures=0,
            last_check=now
        )
        db.add(target1)
        db.flush()

        target2 = ProbeTarget(
            name="示例服务-间歇故障",
            group_id=group1.id,
            type="http",
            address="https://httpbin.org/status/200,500",
            interval=8,
            timeout=5,
            expected_status="200",
            status="degraded",
            consecutive_failures=3,
            consecutive_successes=0,
            last_check=now
        )
        db.add(target2)
        db.flush()

        target3 = ProbeTarget(
            name="示例服务-不可达",
            group_id=group2.id,
            type="tcp",
            address="192.0.2.1:9999",
            interval=15,
            timeout=3,
            expected_status=None,
            status="down",
            consecutive_failures=10,
            consecutive_successes=0,
            last_check=now
        )
        db.add(target3)
        db.flush()

        target4 = ProbeTarget(
            name="测试环境-API网关",
            group_id=group2.id,
            type="http",
            address="https://httpbin.org/status/200",
            interval=12,
            timeout=5,
            expected_status="200",
            status="healthy",
            consecutive_successes=5,
            consecutive_failures=0,
            last_check=now
        )
        db.add(target4)
        db.flush()

        target5 = ProbeTarget(
            name="内部文档服务",
            group_id=group3.id,
            type="http",
            address="https://httpbin.org/status/200",
            interval=30,
            timeout=10,
            expected_status="200",
            status="healthy",
            consecutive_successes=100,
            consecutive_failures=0,
            last_check=now
        )
        db.add(target5)
        db.flush()

        for i in range(20):
            t = now - timedelta(minutes=i * 2)
            db.add(ProbeResult(
                target_id=target1.id,
                timestamp=t,
                success=True,
                latency_ms=50 + i * 2 + (i % 3) * 10
            ))

        for i in range(20):
            t = now - timedelta(minutes=i * 2)
            success = i % 3 != 0
            db.add(ProbeResult(
                target_id=target2.id,
                timestamp=t,
                success=success,
                latency_ms=80 + i * 3 if success else None,
                error_message=None if success else "Status code mismatch: expected 200, got 500"
            ))

        for i in range(20):
            t = now - timedelta(minutes=i * 2)
            db.add(ProbeResult(
                target_id=target3.id,
                timestamp=t,
                success=False,
                latency_ms=3000,
                error_message="Connection timeout"
            ))

        for i in range(20):
            t = now - timedelta(minutes=i * 2)
            success = True
            db.add(ProbeResult(
                target_id=target4.id,
                timestamp=t,
                success=success,
                latency_ms=120 + i * 1.5 + (i % 4) * 8,
                error_message=None
            ))

        for i in range(20):
            t = now - timedelta(minutes=i * 2)
            success = i % 10 != 0
            db.add(ProbeResult(
                target_id=target5.id,
                timestamp=t,
                success=success,
                latency_ms=200 + i * 2 if success else None,
                error_message=None if success else "Service temporarily unavailable"
            ))

        db.add(Alert(
            target_id=target2.id,
            timestamp=now - timedelta(minutes=30),
            from_status="healthy",
            to_status="degraded",
            acknowledged=False
        ))
        db.add(Alert(
            target_id=target3.id,
            timestamp=now - timedelta(minutes=45),
            from_status="healthy",
            to_status="degraded",
            acknowledged=True,
            acknowledged_at=now - timedelta(minutes=40)
        ))
        db.add(Alert(
            target_id=target3.id,
            timestamp=now - timedelta(minutes=35),
            from_status="degraded",
            to_status="down",
            acknowledged=False
        ))

        dep1 = Dependency(
            upstream_id=target1.id,
            downstream_id=target2.id,
            description="示例服务依赖"
        )
        db.add(dep1)

        dep2 = Dependency(
            upstream_id=target2.id,
            downstream_id=target4.id,
            description="API网关依赖核心服务"
        )
        db.add(dep2)

        dep3 = Dependency(
            upstream_id=target4.id,
            downstream_id=target5.id,
            description="内部服务依赖API网关"
        )
        db.add(dep3)

        db.commit()
    except Exception as e:
        print(f"Demo data init error: {e}")
        db.rollback()
    finally:
        db.close()


def _init_demo_rules():
    db = next(get_db())
    try:
        rule_count = db.query(ProbeRule).count()
        if rule_count > 0:
            return

        now = datetime.utcnow()

        rule1 = ProbeRule(
            name="Web应用完整健康检查",
            description="HTTP 200 + 关键词匹配 + 数据库端口连通，三步全过才健康",
            created_at=now,
            updated_at=now,
        )
        db.add(rule1)
        db.flush()

        version1 = ProbeRuleVersion(
            rule_id=rule1.id,
            version=1,
            execution_mode="sequence",
            created_at=now,
        )
        db.add(version1)
        db.flush()

        step1 = ProbeRuleStep(
            version_id=version1.id,
            step_order=0,
            name="首页HTTP状态码",
            step_type="http_status",
            config={"url": "https://httpbin.org/status/200", "method": "GET", "follow_redirects": False},
            timeout=5,
            pass_condition={"expected_codes": ["200", "201", "200-399"]},
            created_at=now,
        )
        step2 = ProbeRuleStep(
            version_id=version1.id,
            step_order=1,
            name="响应体关键词匹配",
            step_type="http_body_match",
            config={"url": "https://httpbin.org/html", "method": "GET", "follow_redirects": True},
            timeout=8,
            pass_condition={"mode": "contains_any", "patterns": ["Herman", "Moby", "httpbin"]},
            created_at=now,
        )
        step3 = ProbeRuleStep(
            version_id=version1.id,
            step_order=2,
            name="数据库TCP端口",
            step_type="tcp_connect",
            config={"address": "httpbin.org:443"},
            timeout=5,
            pass_condition={},
            created_at=now,
        )
        db.add_all([step1, step2, step3])
        db.flush()

        rule1.current_version_id = version1.id

        rule2 = ProbeRule(
            name="多节点高可用探测",
            description="并行探测三个节点，任一可用即判定健康",
            created_at=now,
            updated_at=now,
        )
        db.add(rule2)
        db.flush()

        version2 = ProbeRuleVersion(
            rule_id=rule2.id,
            version=1,
            execution_mode="parallel",
            created_at=now,
        )
        db.add(version2)
        db.flush()

        pstep1 = ProbeRuleStep(
            version_id=version2.id,
            step_order=0,
            name="节点A",
            step_type="http_status",
            config={"url": "https://httpbin.org/status/200", "method": "GET"},
            timeout=5,
            pass_condition={"expected_codes": ["200"]},
            created_at=now,
        )
        pstep2 = ProbeRuleStep(
            version_id=version2.id,
            step_order=1,
            name="节点B",
            step_type="http_status",
            config={"url": "https://httpbin.org/status/200", "method": "GET"},
            timeout=5,
            pass_condition={"expected_codes": ["200"]},
            created_at=now,
        )
        pstep3 = ProbeRuleStep(
            version_id=version2.id,
            step_order=2,
            name="DNS解析验证",
            step_type="dns_resolve",
            config={"domain": "httpbin.org"},
            timeout=5,
            pass_condition={},
            created_at=now,
        )
        db.add_all([pstep1, pstep2, pstep3])
        db.flush()

        rule2.current_version_id = version2.id

        rule3 = ProbeRule(
            name="延迟敏感型API检查",
            description="检查API延迟是否在阈值以内",
            created_at=now,
            updated_at=now,
        )
        db.add(rule3)
        db.flush()

        version3 = ProbeRuleVersion(
            rule_id=rule3.id,
            version=1,
            execution_mode="sequence",
            created_at=now,
        )
        db.add(version3)
        db.flush()

        lstep1 = ProbeRuleStep(
            version_id=version3.id,
            step_order=0,
            name="API响应延迟检查",
            step_type="latency_threshold",
            config={"step_type": "http_status", "config": {"url": "https://httpbin.org/delay/1", "method": "GET"}},
            timeout=10,
            pass_condition={"max_latency_ms": 3000},
            created_at=now,
        )
        db.add(lstep1)
        db.flush()

        rule3.current_version_id = version3.id

        db.commit()
        print("Demo rules initialized")
    except Exception as e:
        print(f"Demo rules init error: {e}")
        db.rollback()
    finally:
        db.close()


def _init_demo_observers():
    db = next(get_db())
    try:
        observer_count = db.query(ObservationPoint).count()
        now = datetime.utcnow()

        if observer_count > 0:
            degraded_target = db.query(ProbeTarget).filter(ProbeTarget.name.like("%间歇%")).first()
            down_target = db.query(ProbeTarget).filter(ProbeTarget.name.like("%不可达%")).first()
            offline_observer = db.query(ObservationPoint).filter(ObservationPoint.status == "offline").first()
            healthy_target = db.query(ProbeTarget).filter(ProbeTarget.name.like("%健康%")).first()

            if degraded_target:
                observer_engine.set_target_simulation_state(degraded_target.id, {
                    "global_failure": False,
                    "partial_fail_regions": ["华南"],
                    "observer_offline_ids": [],
                })
            if down_target:
                observer_engine.set_target_simulation_state(down_target.id, {
                    "global_failure": True,
                    "partial_fail_regions": [],
                    "observer_offline_ids": [],
                })
            if offline_observer and healthy_target:
                observer_engine.set_target_simulation_state(healthy_target.id, {
                    "global_failure": False,
                    "partial_fail_regions": [],
                    "observer_offline_ids": [offline_observer.id],
                })
            return

        now = datetime.utcnow()

        observers_data = [
            {"name": "北京观测点", "region": "华北", "status": "online", "description": "北京机房主观测点"},
            {"name": "上海观测点", "region": "华东", "status": "online", "description": "上海张江机房观测点"},
            {"name": "广州观测点", "region": "华南", "status": "online", "description": "广州南沙机房观测点"},
            {"name": "成都观测点", "region": "西南", "status": "online", "description": "成都西部数据中心"},
            {"name": "新加坡观测点", "region": "海外-新加坡", "status": "online", "description": "东南亚海外观测点"},
            {"name": "美西观测点", "region": "海外-美国", "status": "offline", "description": "硅谷观测点（演示离线状态）"},
        ]

        observer_ids = []
        for od in observers_data:
            heartbeat_time = now if od["status"] == "online" else now - timedelta(hours=2)
            obs = ObservationPoint(
                name=od["name"],
                region=od["region"],
                status=od["status"],
                description=od["description"],
                last_heartbeat=heartbeat_time,
                created_at=now,
                updated_at=now,
            )
            db.add(obs)
            db.flush()
            observer_ids.append(obs.id)

        targets = db.query(ProbeTarget).all()
        for target in targets:
            for oid in observer_ids:
                binding = TargetObserverBinding(
                    target_id=target.id,
                    observer_id=oid,
                    created_at=now,
                )
                db.add(binding)

        db.flush()

        import uuid
        offline_observer = db.query(ObservationPoint).filter(ObservationPoint.status == "offline").first()
        healthy_target = db.query(ProbeTarget).filter(ProbeTarget.name.like("%健康%")).first()
        degraded_target = db.query(ProbeTarget).filter(ProbeTarget.status == "degraded").first()
        down_target = db.query(ProbeTarget).filter(ProbeTarget.status == "down").first()

        all_observers = db.query(ObservationPoint).all()
        online_observers = [o for o in all_observers if o.status == "online"]

        for i in range(5):
            t = now - timedelta(minutes=i * 3)
            round_id = f"rnd_demo_h_{i}"

            for obs in online_observers:
                latency = {
                    "华北": 30, "华东": 25, "华南": 35, "西南": 50, "海外-新加坡": 120
                }.get(obs.region, 40) + (i % 3) * 5

                db.add(ObserverProbeResult(
                    target_id=healthy_target.id if healthy_target else 1,
                    observer_id=obs.id,
                    round_id=round_id,
                    timestamp=t,
                    success=True,
                    latency_ms=latency,
                    error_message=None,
                ))

        if degraded_target:
            for i in range(5):
                t = now - timedelta(minutes=i * 3)
                round_id = f"rnd_demo_d_{i}"

                for obs in online_observers:
                    is_fail_region = obs.region in ["华南"]
                    latency = {
                        "华北": 30, "华东": 25, "华南": 35, "西南": 50, "海外-新加坡": 120
                    }.get(obs.region, 40) + (i % 3) * 5

                    db.add(ObserverProbeResult(
                        target_id=degraded_target.id,
                        observer_id=obs.id,
                        round_id=round_id,
                        timestamp=t,
                        success=not is_fail_region,
                        latency_ms=latency if not is_fail_region else latency * 2,
                        error_message=None if not is_fail_region else f"Region {obs.region} access failed (simulated regional failure)",
                    ))

            observer_engine.set_target_simulation_state(degraded_target.id, {
                "global_failure": False,
                "partial_fail_regions": ["华南"],
                "observer_offline_ids": [],
            })

        if down_target:
            for i in range(5):
                t = now - timedelta(minutes=i * 3)
                round_id = f"rnd_demo_down_{i}"

                for obs in online_observers:
                    latency = {
                        "华北": 30, "华东": 25, "华南": 35, "西南": 50, "海外-新加坡": 120
                    }.get(obs.region, 40) * 3

                    db.add(ObserverProbeResult(
                        target_id=down_target.id,
                        observer_id=obs.id,
                        round_id=round_id,
                        timestamp=t,
                        success=False,
                        latency_ms=latency,
                        error_message="Service unavailable (simulated global failure)",
                    ))

            observer_engine.set_target_simulation_state(down_target.id, {
                "global_failure": True,
                "partial_fail_regions": [],
                "observer_offline_ids": [],
            })

        if offline_observer and healthy_target:
            observer_engine.set_target_simulation_state(healthy_target.id, {
                "global_failure": False,
                "partial_fail_regions": [],
                "observer_offline_ids": [offline_observer.id],
            })

        db.commit()
        print("Demo observers initialized")
    except Exception as e:
        print(f"Demo observers init error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


def _rule_to_response(rule: ProbeRule, db: Session) -> dict:
    versions = []
    for v in sorted(rule.versions, key=lambda x: x.version, reverse=True):
        steps = []
        for s in sorted(v.steps, key=lambda x: x.step_order):
            steps.append({
                "id": s.id,
                "version_id": s.version_id,
                "step_order": s.step_order,
                "name": s.name,
                "step_type": s.step_type,
                "config": s.config,
                "timeout": s.timeout,
                "pass_condition": s.pass_condition,
                "created_at": s.created_at,
            })
        versions.append({
            "id": v.id,
            "rule_id": v.rule_id,
            "version": v.version,
            "execution_mode": v.execution_mode,
            "created_at": v.created_at,
            "steps": steps,
        })

    current_version_obj = None
    if rule.current_version_id:
        for v in versions:
            if v["id"] == rule.current_version_id:
                current_version_obj = v
                break

    bound_count = db.query(ProbeTarget).filter(ProbeTarget.rule_id == rule.id).count()

    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "current_version_id": rule.current_version_id,
        "current_version": current_version_obj["version"] if current_version_obj else None,
        "execution_mode": current_version_obj["execution_mode"] if current_version_obj else None,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
        "versions": versions,
        "bound_target_count": bound_count,
    }


@app.get("/api/rules", response_model=List[ProbeRuleResponse])
def list_rules(db: Session = Depends(get_db)):
    rules = db.query(ProbeRule).order_by(ProbeRule.id.asc()).all()
    return [_rule_to_response(r, db) for r in rules]


@app.get("/api/rules/{rule_id}", response_model=ProbeRuleResponse)
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(ProbeRule).filter(ProbeRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return _rule_to_response(rule, db)


@app.post("/api/rules", response_model=ProbeRuleResponse)
def create_rule(rule_create: ProbeRuleCreate, db: Session = Depends(get_db)):
    now = datetime.utcnow()

    rule = ProbeRule(
        name=rule_create.name,
        description=rule_create.description,
        created_at=now,
        updated_at=now,
    )
    db.add(rule)
    db.flush()

    version = ProbeRuleVersion(
        rule_id=rule.id,
        version=1,
        execution_mode=rule_create.execution_mode or "sequence",
        created_at=now,
    )
    db.add(version)
    db.flush()

    for idx, step_data in enumerate(rule_create.steps):
        step = ProbeRuleStep(
            version_id=version.id,
            step_order=step_data.step_order if step_data.step_order != 0 else idx,
            name=step_data.name,
            step_type=step_data.step_type,
            config=step_data.config,
            timeout=step_data.timeout,
            pass_condition=step_data.pass_condition,
            created_at=now,
        )
        db.add(step)

    db.flush()
    rule.current_version_id = version.id
    db.commit()

    db.refresh(rule)
    return _rule_to_response(rule, db)


@app.put("/api/rules/{rule_id}", response_model=ProbeRuleResponse)
def update_rule(rule_id: int, rule_update: ProbeRuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(ProbeRule).filter(ProbeRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    now = datetime.utcnow()
    needs_new_version = rule_update.execution_mode is not None or rule_update.steps is not None

    if rule_update.name is not None:
        rule.name = rule_update.name
    if rule_update.description is not None:
        rule.description = rule_update.description

    if needs_new_version:
        last_version = db.query(ProbeRuleVersion).filter(
            ProbeRuleVersion.rule_id == rule.id
        ).order_by(ProbeRuleVersion.version.desc()).first()
        new_version_num = (last_version.version + 1) if last_version else 1

        execution_mode = rule_update.execution_mode
        if execution_mode is None and last_version:
            execution_mode = last_version.execution_mode
        if execution_mode is None:
            execution_mode = "sequence"

        new_version = ProbeRuleVersion(
            rule_id=rule.id,
            version=new_version_num,
            execution_mode=execution_mode,
            created_at=now,
        )
        db.add(new_version)
        db.flush()

        if rule_update.steps is not None:
            for idx, step_data in enumerate(rule_update.steps):
                step = ProbeRuleStep(
                    version_id=new_version.id,
                    step_order=step_data.step_order if step_data.step_order != 0 else idx,
                    name=step_data.name,
                    step_type=step_data.step_type,
                    config=step_data.config,
                    timeout=step_data.timeout,
                    pass_condition=step_data.pass_condition,
                    created_at=now,
                )
                db.add(step)
        elif last_version:
            for old_step in sorted(last_version.steps, key=lambda x: x.step_order):
                step = ProbeRuleStep(
                    version_id=new_version.id,
                    step_order=old_step.step_order,
                    name=old_step.name,
                    step_type=old_step.step_type,
                    config=old_step.config,
                    timeout=old_step.timeout,
                    pass_condition=old_step.pass_condition,
                    created_at=now,
                )
                db.add(step)

        db.flush()
        rule.current_version_id = new_version.id

    rule.updated_at = now
    db.commit()
    db.refresh(rule)
    return _rule_to_response(rule, db)


@app.delete("/api/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(ProbeRule).filter(ProbeRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    bound_targets = db.query(ProbeTarget).filter(ProbeTarget.rule_id == rule_id).all()
    for t in bound_targets:
        t.rule_id = None

    db.delete(rule)
    db.commit()
    return {"message": "Rule deleted"}


@app.get("/api/targets/{target_id}/rule-executions")
def get_target_rule_executions(
    target_id: int,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    executions = db.query(ProbeRuleExecution).options(
        joinedload(ProbeRuleExecution.step_executions),
        joinedload(ProbeRuleExecution.version),
    ).filter(
        ProbeRuleExecution.target_id == target_id
    ).order_by(ProbeRuleExecution.timestamp.desc()).limit(limit).all()

    result = []
    for exec in reversed(executions):
        step_execs = []
        step_map = {}
        for se in exec.step_executions:
            step_execs.append({
                "id": se.id,
                "rule_execution_id": se.rule_execution_id,
                "step_id": se.step_id,
                "step_name": None,
                "step_type": None,
                "timestamp": se.timestamp,
                "success": se.success,
                "latency_ms": se.latency_ms,
                "error_message": se.error_message,
                "raw_response": se.raw_response,
            })
            step_map[se.step_id] = len(step_execs) - 1

        if exec.version:
            for step in exec.version.steps:
                if step.id in step_map:
                    idx = step_map[step.id]
                    step_execs[idx]["step_name"] = step.name
                    step_execs[idx]["step_type"] = step.step_type

        failed_step_name = None
        if exec.failed_step_id and exec.version:
            for step in exec.version.steps:
                if step.id == exec.failed_step_id:
                    failed_step_name = step.name
                    break

        result.append({
            "id": exec.id,
            "target_id": exec.target_id,
            "version_id": exec.version_id,
            "version": exec.version.version if exec.version else None,
            "execution_mode": exec.version.execution_mode if exec.version else None,
            "timestamp": exec.timestamp,
            "success": exec.success,
            "latency_ms": exec.latency_ms,
            "error_message": exec.error_message,
            "failed_step_id": exec.failed_step_id,
            "failed_step_name": failed_step_name,
            "step_executions": step_execs,
        })

    return result


@app.get("/api/targets/{target_id}/rule")
def get_target_current_rule(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).options(
        joinedload(ProbeTarget.rule)
    ).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    if not target.rule:
        return {"rule": None, "version": None, "steps": []}

    rule = target.rule
    version = None
    steps = []

    if rule.current_version_id:
        version = db.query(ProbeRuleVersion).filter(
            ProbeRuleVersion.id == rule.current_version_id
        ).first()
    if not version:
        version = db.query(ProbeRuleVersion).filter(
            ProbeRuleVersion.rule_id == rule.id
        ).order_by(ProbeRuleVersion.version.desc()).first()

    if version:
        step_list = db.query(ProbeRuleStep).filter(
            ProbeRuleStep.version_id == version.id
        ).order_by(ProbeRuleStep.step_order.asc()).all()

        step_ids = [s.id for s in step_list]
        last_executions = {}
        if step_ids:
            from sqlalchemy import text as sqltext
            for sid in step_ids:
                last = db.query(ProbeRuleStepExecution).filter(
                    ProbeRuleStepExecution.step_id == sid
                ).order_by(ProbeRuleStepExecution.timestamp.desc()).first()
                if last:
                    last_executions[sid] = {
                        "success": last.success,
                        "latency_ms": last.latency_ms,
                        "error_message": last.error_message,
                        "timestamp": last.timestamp,
                    }

        for s in step_list:
            steps.append({
                "id": s.id,
                "step_order": s.step_order,
                "name": s.name,
                "step_type": s.step_type,
                "config": s.config,
                "timeout": s.timeout,
                "pass_condition": s.pass_condition,
                "last_execution": last_executions.get(s.id),
            })

    return {
        "rule": _rule_to_response(rule, db),
        "version": {
            "id": version.id,
            "version": version.version,
            "execution_mode": version.execution_mode,
            "created_at": version.created_at,
        } if version else None,
        "steps": steps,
        "execution_mode": version.execution_mode if version else None,
    }


@app.get("/api/steps/{step_id}/history")
def get_step_history(
    step_id: int,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    step = db.query(ProbeRuleStep).filter(ProbeRuleStep.id == step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    executions = db.query(ProbeRuleStepExecution).filter(
        ProbeRuleStepExecution.step_id == step_id
    ).order_by(ProbeRuleStepExecution.timestamp.desc()).limit(limit).all()

    return {
        "step_id": step.id,
        "step_name": step.name,
        "step_type": step.step_type,
        "executions": [
            {
                "id": e.id,
                "rule_execution_id": e.rule_execution_id,
                "step_id": e.step_id,
                "step_name": step.name,
                "step_type": step.step_type,
                "timestamp": e.timestamp,
                "success": e.success,
                "latency_ms": e.latency_ms,
                "error_message": e.error_message,
                "raw_response": e.raw_response,
            }
            for e in executions
        ],
    }


@app.get("/api/groups", response_model=List[ProbeGroupResponse])
def list_groups(db: Session = Depends(get_db)):
    groups = db.query(ProbeGroup).order_by(ProbeGroup.id.asc()).all()
    return groups


@app.get("/api/groups/{group_id}", response_model=ProbeGroupWithTargetsResponse)
def get_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@app.post("/api/groups", response_model=ProbeGroupResponse)
def create_group(group: ProbeGroupCreate, db: Session = Depends(get_db)):
    db_group = ProbeGroup(**group.model_dump())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group


@app.put("/api/groups/{group_id}", response_model=ProbeGroupResponse)
def update_group(group_id: int, group_update: ProbeGroupUpdate, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    update_data = group_update.model_dump(exclude_unset=True)

    threshold_fields = ["degrade_threshold", "down_threshold", "success_threshold"]
    has_threshold_change = any(field in update_data for field in threshold_fields)

    for key, value in update_data.items():
        setattr(group, key, value)

    if has_threshold_change:
        for target in group.targets:
            if "degrade_threshold" in update_data:
                target.degrade_threshold = group.degrade_threshold
            if "down_threshold" in update_data:
                target.down_threshold = group.down_threshold
            if "success_threshold" in update_data:
                target.success_threshold = group.success_threshold

    db.commit()
    db.refresh(group)
    return group


@app.delete("/api/groups/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for target in group.targets:
        target.group_id = None
        probe_engine.remove_target(target.id)
        probe_engine.add_target(target.id)

    db.delete(group)
    db.commit()
    return {"message": "Group deleted"}


@app.post("/api/groups/{group_id}/pause")
def pause_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for target in group.targets:
        if not target.paused:
            target.paused = True
            probe_engine.toggle_target(target.id, True)

    db.commit()
    return {"message": "Group paused"}


@app.post("/api/groups/{group_id}/resume")
def resume_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for target in group.targets:
        if target.paused:
            target.paused = False
            probe_engine.toggle_target(target.id, False)

    db.commit()
    return {"message": "Group resumed"}


@app.post("/api/groups/{group_id}/silence")
def silence_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for target in group.targets:
        target.silenced = True

    db.commit()
    return {"message": "Group silenced"}


@app.post("/api/groups/{group_id}/unsilence")
def unsilence_group(group_id: int, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for target in group.targets:
        target.silenced = False

    db.commit()
    return {"message": "Group unsilenced"}


@app.post("/api/groups/{group_id}/apply-thresholds")
def apply_group_thresholds(group_id: int, db: Session = Depends(get_db)):
    group = db.query(ProbeGroup).filter(ProbeGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    for target in group.targets:
        target.degrade_threshold = group.degrade_threshold
        target.down_threshold = group.down_threshold
        target.success_threshold = group.success_threshold

    db.commit()
    return {"message": "Thresholds applied to all targets in group"}


@app.get("/api/targets", response_model=List[ProbeTargetResponse])
def list_targets(db: Session = Depends(get_db)):
    targets = db.query(ProbeTarget).options(
        joinedload(ProbeTarget.group),
        joinedload(ProbeTarget.rule),
    ).order_by(ProbeTarget.id.asc()).all()
    return [_enrich_target(t, db) for t in targets]


@app.post("/api/targets", response_model=ProbeTargetResponse)
def create_target(target: ProbeTargetCreate, db: Session = Depends(get_db)):
    db_target = ProbeTarget(**target.model_dump())
    db.add(db_target)
    db.commit()
    db.refresh(db_target)
    probe_engine.add_target(db_target.id)
    db_target = db.query(ProbeTarget).options(
        joinedload(ProbeTarget.group),
        joinedload(ProbeTarget.rule),
    ).filter(ProbeTarget.id == db_target.id).first()
    return _enrich_target(db_target, db)


@app.get("/api/targets/{target_id}", response_model=ProbeTargetResponse)
def get_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).options(
        joinedload(ProbeTarget.group),
        joinedload(ProbeTarget.rule),
    ).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return _enrich_target(target, db)


@app.put("/api/targets/{target_id}", response_model=ProbeTargetResponse)
def update_target(target_id: int, target_update: ProbeTargetUpdate, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).options(
        joinedload(ProbeTarget.group),
        joinedload(ProbeTarget.rule),
    ).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    old_paused = target.paused

    update_data = target_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(target, key, value)

    db.commit()
    db.refresh(target)

    if "paused" in update_data and old_paused != target.paused:
        probe_engine.toggle_target(target.id, target.paused)

    return _enrich_target(target, db)


@app.delete("/api/targets/{target_id}")
def delete_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    probe_engine.remove_target(target_id)
    db.delete(target)
    db.commit()
    return {"message": "Target deleted"}


@app.post("/api/targets/{target_id}/pause")
def pause_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    target.paused = True
    db.commit()
    probe_engine.toggle_target(target_id, True)
    return {"message": "Target paused"}


@app.post("/api/targets/{target_id}/resume")
def resume_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    target.paused = False
    db.commit()
    probe_engine.toggle_target(target_id, False)
    return {"message": "Target resumed"}


@app.post("/api/targets/{target_id}/silence")
def silence_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    target.silenced = True
    db.commit()
    return {"message": "Target silenced"}


@app.post("/api/targets/{target_id}/unsilence")
def unsilence_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    target.silenced = False
    db.commit()
    return {"message": "Target unsilenced"}


@app.get("/api/targets/{target_id}/results", response_model=List[ProbeResultResponse])
def get_target_results(target_id: int, limit: int = 100, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    results = db.query(ProbeResult).filter(
        ProbeResult.target_id == target_id
    ).order_by(ProbeResult.timestamp.desc()).limit(limit).all()

    return list(reversed(results))


@app.get("/api/targets/{target_id}/history")
async def get_target_history_api(target_id: int, hours: int = 24):
    return await get_target_history(target_id, hours)


@app.get("/api/alerts", response_model=List[AlertResponse])
def list_alerts(limit: int = 50, db: Session = Depends(get_db)):
    alerts = db.query(Alert).order_by(Alert.timestamp.desc()).limit(limit).all()
    result = []
    for alert in alerts:
        alert_dict = {
            "id": alert.id,
            "target_id": alert.target_id,
            "target_name": alert.target.name if alert.target else None,
            "timestamp": alert.timestamp,
            "from_status": alert.from_status,
            "to_status": alert.to_status,
            "acknowledged": alert.acknowledged,
            "acknowledged_at": alert.acknowledged_at
        }
        result.append(alert_dict)
    return result


@app.put("/api/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, ack: AlertAcknowledge, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.acknowledged = ack.acknowledged
    if ack.acknowledged:
        alert.acknowledged_at = datetime.utcnow()
    else:
        alert.acknowledged_at = None

    db.commit()
    return {"message": "Alert updated"}


def _get_downstream_targets(db: Session, target_id: int) -> List[ProbeTarget]:
    visited = set()
    result = []
    queue = deque([target_id])

    while queue:
        current_id = queue.popleft()
        if current_id in visited:
            continue
        visited.add(current_id)

        deps = db.query(Dependency).filter(Dependency.upstream_id == current_id).all()
        for dep in deps:
            if dep.downstream_id not in visited:
                downstream = db.query(ProbeTarget).filter(ProbeTarget.id == dep.downstream_id).first()
                if downstream:
                    result.append(downstream)
                    queue.append(dep.downstream_id)

    return result


def _get_upstream_targets(db: Session, target_id: int) -> List[ProbeTarget]:
    visited = set()
    result = []
    queue = deque([target_id])

    while queue:
        current_id = queue.popleft()
        if current_id in visited:
            continue
        visited.add(current_id)

        deps = db.query(Dependency).filter(Dependency.downstream_id == current_id).all()
        for dep in deps:
            if dep.upstream_id not in visited:
                upstream = db.query(ProbeTarget).filter(ProbeTarget.id == dep.upstream_id).first()
                if upstream:
                    result.append(upstream)
                    queue.append(dep.upstream_id)

    return result


def _update_cascade_status(db: Session, upstream_target: ProbeTarget):
    if upstream_target.status == "down" or upstream_target.status == "degraded":
        downstream_targets = _get_downstream_targets(db, upstream_target.id)
        for target in downstream_targets:
            if not target.cascade_affected:
                target.cascade_affected = True
                target.cascade_source_id = upstream_target.id
                if not target.paused:
                    target.paused = True
                    probe_engine.toggle_target(target.id, True)
    else:
        downstream_targets = _get_downstream_targets(db, upstream_target.id)
        for target in downstream_targets:
            upstreams = _get_upstream_targets(db, target.id)
            has_failed_upstream = any(
                u.status in ("down", "degraded") for u in upstreams
            )
            if not has_failed_upstream and target.cascade_affected:
                target.cascade_affected = False
                target.cascade_source_id = None
                if target.paused:
                    target.paused = False
                    probe_engine.toggle_target(target.id, False)


@app.get("/api/dependencies", response_model=List[DependencyWithNamesResponse])
def list_dependencies(db: Session = Depends(get_db)):
    deps = db.query(Dependency).order_by(Dependency.id.asc()).all()
    result = []
    for dep in deps:
        result.append({
            "id": dep.id,
            "upstream_id": dep.upstream_id,
            "upstream_name": dep.upstream_target.name if dep.upstream_target else "",
            "downstream_id": dep.downstream_id,
            "downstream_name": dep.downstream_target.name if dep.downstream_target else "",
            "description": dep.description,
            "created_at": dep.created_at
        })
    return result


@app.post("/api/dependencies", response_model=DependencyResponse)
def create_dependency(dep: DependencyCreate, db: Session = Depends(get_db)):
    if dep.upstream_id == dep.downstream_id:
        raise HTTPException(status_code=400, detail="Cannot create dependency with same target")

    upstream = db.query(ProbeTarget).filter(ProbeTarget.id == dep.upstream_id).first()
    downstream = db.query(ProbeTarget).filter(ProbeTarget.id == dep.downstream_id).first()
    if not upstream or not downstream:
        raise HTTPException(status_code=404, detail="Target not found")

    existing = db.query(Dependency).filter(
        Dependency.upstream_id == dep.upstream_id,
        Dependency.downstream_id == dep.downstream_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Dependency already exists")

    db_dep = Dependency(**dep.model_dump())
    db.add(db_dep)
    db.commit()
    db.refresh(db_dep)

    _update_cascade_status(db, upstream)
    db.commit()

    manager.broadcast_dependencies()
    manager.broadcast_targets()

    return db_dep


@app.delete("/api/dependencies/{dep_id}")
def delete_dependency(dep_id: int, db: Session = Depends(get_db)):
    dep = db.query(Dependency).filter(Dependency.id == dep_id).first()
    if not dep:
        raise HTTPException(status_code=404, detail="Dependency not found")

    downstream_id = dep.downstream_id
    downstream_target = db.query(ProbeTarget).filter(
        ProbeTarget.id == downstream_id
    ).first()

    affected_target_ids = []
    if downstream_target and downstream_target.cascade_affected:
        affected = _get_downstream_targets(db, downstream_id)
        affected_target_ids = [t.id for t in affected]
        affected_target_ids.append(downstream_id)

    db.delete(dep)
    db.commit()

    for target_id in affected_target_ids:
        target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
        if target and target.cascade_affected:
            upstreams = _get_upstream_targets(db, target_id)
            has_failed_upstream = any(
                u.status in ("down", "degraded") for u in upstreams
            )
            if not has_failed_upstream:
                target.cascade_affected = False
                target.cascade_source_id = None
                if target.paused:
                    target.paused = False
                    probe_engine.add_target(target.id)

    db.commit()

    manager.broadcast_dependencies()
    manager.broadcast_targets()

    return {"message": "Dependency deleted"}


@app.get("/api/dependencies/simulate/{target_id}", response_model=CascadeSimulationResponse)
def simulate_cascade(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    downstream = _get_downstream_targets(db, target_id)
    return {
        "source_target_id": target_id,
        "affected_target_ids": [t.id for t in downstream],
        "affected_target_names": [t.name for t in downstream]
    }


def _enrich_maintenance_window(window: MaintenanceWindow, db: Session = None) -> dict:
    target_name = None
    group_name = None
    if window.target:
        target_name = window.target.name
    elif db:
        target = db.query(ProbeTarget).filter(ProbeTarget.id == window.target_id).first()
        if target:
            target_name = target.name

    if window.group:
        group_name = window.group.name
    elif window.group_id and db:
        group = db.query(ProbeGroup).filter(ProbeGroup.id == window.group_id).first()
        if group:
            group_name = group.name

    events = []
    for event in window.events:
        events.append({
            "id": event.id,
            "window_id": event.window_id,
            "event_type": event.event_type,
            "message": event.message,
            "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            "extra_data": event.extra_data
        })

    return {
        "id": window.id,
        "target_id": window.target_id,
        "target_name": target_name,
        "group_id": window.group_id,
        "group_name": group_name,
        "title": window.title,
        "description": window.description,
        "start_time": window.start_time.isoformat(),
        "end_time": window.end_time.isoformat(),
        "reason": window.reason,
        "owner": window.owner,
        "status": window.status,
        "is_cancelled": window.is_cancelled or False,
        "cancelled_at": window.cancelled_at.isoformat() if window.cancelled_at else None,
        "cancelled_reason": window.cancelled_reason,
        "actual_start_time": window.actual_start_time.isoformat() if window.actual_start_time else None,
        "actual_end_time": window.actual_end_time.isoformat() if window.actual_end_time else None,
        "timeout_alert_sent": window.timeout_alert_sent or False,
        "extension_reason": window.extension_reason,
        "created_by": window.created_by,
        "created_at": window.created_at.isoformat(),
        "updated_at": window.updated_at.isoformat(),
        "events": events
    }


@app.get("/api/maintenance-windows", response_model=MaintenanceWindowListResponse)
def list_maintenance_windows(
    target_id: Optional[int] = None,
    group_id: Optional[int] = None,
    status: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(MaintenanceWindow).options(
        joinedload(MaintenanceWindow.target),
        joinedload(MaintenanceWindow.group),
        joinedload(MaintenanceWindow.events)
    )

    if target_id:
        query = query.filter(MaintenanceWindow.target_id == target_id)
    if group_id:
        query = query.filter(MaintenanceWindow.group_id == group_id)
    if status:
        query = query.filter(MaintenanceWindow.status == status)
    if start_time:
        query = query.filter(MaintenanceWindow.end_time >= start_time)
    if end_time:
        query = query.filter(MaintenanceWindow.start_time <= end_time)

    total = query.count()
    windows = query.order_by(MaintenanceWindow.start_time.desc()).offset(offset).limit(limit).all()

    items = [_enrich_maintenance_window(w, db) for w in windows]
    return {"items": items, "total": total}


@app.get("/api/maintenance-windows/calendar", response_model=MaintenanceWindowCalendarResponse)
def get_maintenance_calendar(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    target_id: Optional[int] = None,
    group_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    windows = maintenance_engine.get_windows_for_calendar(
        start_time=start_time,
        end_time=end_time,
        target_id=target_id,
        group_id=group_id
    )

    targets_query = db.query(ProbeTarget).filter(ProbeTarget.deprecated == False)
    if group_id:
        targets_query = targets_query.filter(ProbeTarget.group_id == group_id)
    targets = targets_query.order_by(ProbeTarget.name).all()

    targets_data = []
    for t in targets:
        group_color = t.group.color if t.group else "#3b82f6"
        targets_data.append({
            "id": t.id,
            "name": t.name,
            "group_id": t.group_id,
            "group_name": t.group.name if t.group else None,
            "status": t.status,
            "paused": t.paused,
            "color": group_color
        })

    return {"windows": windows, "targets": targets_data}


@app.get("/api/maintenance-windows/{window_id}", response_model=MaintenanceWindowResponse)
def get_maintenance_window(window_id: int, db: Session = Depends(get_db)):
    window = db.query(MaintenanceWindow).options(
        joinedload(MaintenanceWindow.target),
        joinedload(MaintenanceWindow.group),
        joinedload(MaintenanceWindow.events)
    ).filter(MaintenanceWindow.id == window_id).first()
    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")
    return _enrich_maintenance_window(window, db)


@app.post("/api/maintenance-windows", response_model=MaintenanceWindowResponse)
def create_maintenance_window(window_data: MaintenanceWindowCreate, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == window_data.target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    if window_data.start_time >= window_data.end_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")

    if maintenance_engine.check_overlap(window_data.target_id, window_data.start_time, window_data.end_time):
        raise HTTPException(status_code=409, detail="Maintenance window overlaps with an existing window for this target")

    group_id = target.group_id

    window = MaintenanceWindow(
        target_id=window_data.target_id,
        group_id=group_id,
        title=window_data.title,
        description=window_data.description,
        start_time=window_data.start_time,
        end_time=window_data.end_time,
        reason=window_data.reason,
        owner=window_data.owner,
        created_by=window_data.created_by,
        status="scheduled"
    )
    db.add(window)
    db.flush()

    event = MaintenanceWindowEvent(
        window_id=window.id,
        event_type="created",
        message=f"维护窗口已创建：{window.title}"
    )
    db.add(event)

    db.commit()
    db.refresh(window)

    manager.broadcast_maintenance_update()

    return _enrich_maintenance_window(window, db)


@app.put("/api/maintenance-windows/{window_id}", response_model=MaintenanceWindowResponse)
def update_maintenance_window(window_id: int, window_data: MaintenanceWindowUpdate, db: Session = Depends(get_db)):
    window = db.query(MaintenanceWindow).filter(MaintenanceWindow.id == window_id).first()
    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")

    if window.status == "completed" or window.is_cancelled:
        raise HTTPException(status_code=400, detail="Cannot update completed or cancelled window")

    new_start = window_data.start_time if window_data.start_time is not None else window.start_time
    new_end = window_data.end_time if window_data.end_time is not None else window.end_time

    if new_start >= new_end:
        raise HTTPException(status_code=400, detail="End time must be after start time")

    if maintenance_engine.check_overlap(window.target_id, new_start, new_end, exclude_window_id=window_id):
        raise HTTPException(status_code=409, detail="Maintenance window overlaps with an existing window for this target")

    if window_data.title is not None:
        window.title = window_data.title
    if window_data.description is not None:
        window.description = window_data.description
    if window_data.start_time is not None:
        window.start_time = window_data.start_time
    if window_data.end_time is not None:
        window.end_time = window_data.end_time
    if window_data.reason is not None:
        window.reason = window_data.reason
    if window_data.owner is not None:
        window.owner = window_data.owner

    db.commit()
    db.refresh(window)

    manager.broadcast_maintenance_update()

    return _enrich_maintenance_window(window, db)


@app.post("/api/maintenance-windows/{window_id}/extend", response_model=MaintenanceWindowResponse)
def extend_maintenance_window(window_id: int, extend_data: MaintenanceWindowExtend, db: Session = Depends(get_db)):
    window = db.query(MaintenanceWindow).filter(MaintenanceWindow.id == window_id).first()
    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")

    if window.status == "completed" or window.is_cancelled:
        raise HTTPException(status_code=400, detail="Cannot extend completed or cancelled window")

    if extend_data.end_time <= window.end_time:
        raise HTTPException(status_code=400, detail="New end time must be after current end time")

    success = maintenance_engine.extend_window(window_id, extend_data.end_time, extend_data.extension_reason)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to extend maintenance window")

    db.refresh(window)
    manager.broadcast_maintenance_update()

    return _enrich_maintenance_window(window, db)


@app.post("/api/maintenance-windows/{window_id}/cancel", response_model=MaintenanceWindowResponse)
def cancel_maintenance_window(window_id: int, cancel_data: MaintenanceWindowCancel, db: Session = Depends(get_db)):
    window = db.query(MaintenanceWindow).filter(MaintenanceWindow.id == window_id).first()
    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")

    success = maintenance_engine.cancel_window(window_id, cancel_data.cancelled_reason)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to cancel maintenance window")

    db.refresh(window)
    manager.broadcast_maintenance_update()

    return _enrich_maintenance_window(window, db)


@app.delete("/api/maintenance-windows/{window_id}")
def delete_maintenance_window(window_id: int, db: Session = Depends(get_db)):
    window = db.query(MaintenanceWindow).filter(MaintenanceWindow.id == window_id).first()
    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")

    if window.status == "active":
        target = db.query(ProbeTarget).filter(ProbeTarget.id == window.target_id).first()
        if target:
            target.paused = False
            target.silenced = False
            probe_engine.toggle_target(target.id, False)

    db.delete(window)
    db.commit()

    manager.broadcast_maintenance_update()

    return {"message": "Maintenance window deleted"}


@app.get("/api/maintenance-windows/{window_id}/events", response_model=List[MaintenanceWindowEventResponse])
def get_maintenance_window_events(window_id: int, db: Session = Depends(get_db)):
    window = db.query(MaintenanceWindow).filter(MaintenanceWindow.id == window_id).first()
    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")

    events = db.query(MaintenanceWindowEvent).filter(
        MaintenanceWindowEvent.window_id == window_id
    ).order_by(MaintenanceWindowEvent.timestamp.asc()).all()

    return events


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)


def _calculate_stats(results):
    if not results:
        return {"availability": 0, "p50": 0, "p95": 0, "p99": 0}
    
    success_count = sum(1 for r in results if r.success)
    availability = (success_count / len(results)) * 100
    
    latencies = [r.latency_ms for r in results if r.success and r.latency_ms is not None]
    latencies.sort()
    
    p50 = p95 = p99 = 0
    if latencies:
        n = len(latencies)
        p50 = latencies[int(n * 0.5)] if n > 0 else 0
        p95 = latencies[int(n * 0.95)] if n > 0 else 0
        p99 = latencies[int(n * 0.99)] if n > 0 else 0
    
    return {"availability": availability, "p50": p50, "p95": p95, "p99": p99}


@app.get("/api/snapshots", response_model=List[SnapshotResponse])
def list_snapshots(
    search: str = "",
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db)
):
    query = db.query(Snapshot)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Snapshot.name.like(search_pattern)) |
            (Snapshot.description.like(search_pattern))
        )
    
    if sort_by == "created_at":
        order_column = Snapshot.created_at
    elif sort_by == "start_time":
        order_column = Snapshot.start_time
    elif sort_by == "name":
        order_column = Snapshot.name
    else:
        order_column = Snapshot.created_at
    
    if sort_order == "desc":
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())
    
    return query.all()


@app.post("/api/snapshots", response_model=SnapshotResponse)
def create_snapshot(snapshot_create: SnapshotCreate, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    
    snapshot = Snapshot(
        name=snapshot_create.name,
        description=snapshot_create.description,
        start_time=snapshot_create.start_time,
        end_time=snapshot_create.end_time,
        created_at=now
    )
    db.add(snapshot)
    db.flush()
    
    results = db.query(ProbeResult).options(
        joinedload(ProbeResult.target)
    ).filter(
        ProbeResult.timestamp >= snapshot_create.start_time,
        ProbeResult.timestamp <= snapshot_create.end_time
    ).order_by(ProbeResult.timestamp.asc()).all()
    
    target_ids = set()
    for result in results:
        if result.target:
            target_ids.add(result.target_id)
            snapshot_data = SnapshotData(
                snapshot_id=snapshot.id,
                target_id=result.target_id,
                target_name=result.target.name,
                timestamp=result.timestamp,
                status=result.target.status if result.target else "unknown",
                latency_ms=result.latency_ms,
                success=result.success,
                consecutive_failures=result.target.consecutive_failures if result.target else 0,
                consecutive_successes=result.target.consecutive_successes if result.target else 0,
                error_message=result.error_message
            )
            db.add(snapshot_data)
    
    alerts = db.query(Alert).options(
        joinedload(Alert.target)
    ).filter(
        Alert.timestamp >= snapshot_create.start_time,
        Alert.timestamp <= snapshot_create.end_time
    ).all()
    
    for alert in alerts:
        if alert.target:
            snapshot_alert = SnapshotAlert(
                snapshot_id=snapshot.id,
                target_id=alert.target_id,
                target_name=alert.target.name,
                timestamp=alert.timestamp,
                from_status=alert.from_status,
                to_status=alert.to_status
            )
            db.add(snapshot_alert)
    
    snapshot.target_count = len(target_ids)
    snapshot.data_point_count = len(results)
    
    db.commit()
    db.refresh(snapshot)
    
    return snapshot


@app.get("/api/snapshots/{snapshot_id}", response_model=SnapshotDetailResponse)
def get_snapshot(snapshot_id: int, db: Session = Depends(get_db)):
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    data = db.query(SnapshotData).filter(
        SnapshotData.snapshot_id == snapshot_id
    ).order_by(SnapshotData.timestamp.asc()).all()
    
    alerts = db.query(SnapshotAlert).filter(
        SnapshotAlert.snapshot_id == snapshot_id
    ).order_by(SnapshotAlert.timestamp.asc()).all()
    
    return {
        "id": snapshot.id,
        "name": snapshot.name,
        "description": snapshot.description,
        "start_time": snapshot.start_time,
        "end_time": snapshot.end_time,
        "target_count": snapshot.target_count,
        "data_point_count": snapshot.data_point_count,
        "created_at": snapshot.created_at,
        "data": data,
        "alerts": alerts
    }


@app.put("/api/snapshots/{snapshot_id}", response_model=SnapshotResponse)
def update_snapshot(snapshot_id: int, snapshot_update: SnapshotUpdate, db: Session = Depends(get_db)):
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    if snapshot_update.name is not None:
        snapshot.name = snapshot_update.name
    if snapshot_update.description is not None:
        snapshot.description = snapshot_update.description
    
    db.commit()
    db.refresh(snapshot)
    
    return snapshot


@app.delete("/api/snapshots/{snapshot_id}")
def delete_snapshot(snapshot_id: int, db: Session = Depends(get_db)):
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    db.delete(snapshot)
    db.commit()
    
    return {"message": "Snapshot deleted"}


@app.get("/api/snapshots/{snapshot_id}/timeline")
def get_snapshot_timeline(snapshot_id: int, db: Session = Depends(get_db)):
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    data = db.query(SnapshotData).filter(
        SnapshotData.snapshot_id == snapshot_id
    ).order_by(SnapshotData.timestamp.asc()).all()
    
    timeline = {}
    for d in data:
        ts = d.timestamp.isoformat()
        if ts not in timeline:
            timeline[ts] = {}
        timeline[ts][d.target_name] = {
            "target_id": d.target_id,
            "status": d.status,
            "latency_ms": d.latency_ms,
            "success": d.success,
            "consecutive_failures": d.consecutive_failures,
            "consecutive_successes": d.consecutive_successes,
            "error_message": d.error_message
        }
    
    alerts = db.query(SnapshotAlert).filter(
        SnapshotAlert.snapshot_id == snapshot_id
    ).order_by(SnapshotAlert.timestamp.asc()).all()
    
    alert_list = []
    for a in alerts:
        alert_list.append({
            "timestamp": a.timestamp.isoformat(),
            "target_id": a.target_id,
            "target_name": a.target_name,
            "from_status": a.from_status,
            "to_status": a.to_status
        })
    
    return {
        "snapshot_id": snapshot_id,
        "start_time": snapshot.start_time.isoformat(),
        "end_time": snapshot.end_time.isoformat(),
        "timeline": timeline,
        "alerts": alert_list
    }


@app.get("/api/snapshots/{snapshot_id}/targets/{target_name}/stats")
def get_snapshot_target_stats(snapshot_id: int, target_name: str, db: Session = Depends(get_db)):
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    data = db.query(SnapshotData).filter(
        SnapshotData.snapshot_id == snapshot_id,
        SnapshotData.target_name == target_name
    ).order_by(SnapshotData.timestamp.asc()).all()
    
    if not data:
        raise HTTPException(status_code=404, detail="Target data not found in snapshot")
    
    results = data
    stats = _calculate_stats(results)
    
    return {
        "target_name": target_name,
        "snapshot_id": snapshot_id,
        "snapshot_name": snapshot.name,
        "stats": stats,
        "data_points": len(data),
        "results": [
            {
                "timestamp": d.timestamp.isoformat(),
                "status": d.status,
                "latency_ms": d.latency_ms,
                "success": d.success
            }
            for d in data
        ]
    }


@app.get("/api/snapshots/compare/{snapshot_a_id}/{snapshot_b_id}")
def compare_snapshots(snapshot_a_id: int, snapshot_b_id: int, db: Session = Depends(get_db)):
    snapshot_a = db.query(Snapshot).filter(Snapshot.id == snapshot_a_id).first()
    snapshot_b = db.query(Snapshot).filter(Snapshot.id == snapshot_b_id).first()
    
    if not snapshot_a or not snapshot_b:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    data_a = db.query(SnapshotData).filter(
        SnapshotData.snapshot_id == snapshot_a_id
    ).all()
    
    data_b = db.query(SnapshotData).filter(
        SnapshotData.snapshot_id == snapshot_b_id
    ).all()
    
    targets_a = {}
    targets_b = {}
    
    for d in data_a:
        if d.target_name not in targets_a:
            targets_a[d.target_name] = []
        targets_a[d.target_name].append(d)
    
    for d in data_b:
        if d.target_name not in targets_b:
            targets_b[d.target_name] = []
        targets_b[d.target_name].append(d)
    
    common_targets = set(targets_a.keys()) & set(targets_b.keys())
    
    comparisons = []
    for target_name in common_targets:
        results_a = targets_a[target_name]
        results_b = targets_b[target_name]
        
        stats_a = _calculate_stats(results_a)
        stats_b = _calculate_stats(results_b)
        
        diff = {
            "availability": stats_b["availability"] - stats_a["availability"],
            "p50": stats_b["p50"] - stats_a["p50"],
            "p95": stats_b["p95"] - stats_a["p95"],
            "p99": stats_b["p99"] - stats_a["p99"],
        }
        
        comparisons.append({
            "target_name": target_name,
            "snapshot_a": {
                "stats": stats_a,
                "data_points": len(results_a),
                "results": [
                    {
                        "timestamp": r.timestamp.isoformat(),
                        "status": r.status,
                        "latency_ms": r.latency_ms,
                        "success": r.success
                    }
                    for r in results_a
                ]
            },
            "snapshot_b": {
                "stats": stats_b,
                "data_points": len(results_b),
                "results": [
                    {
                        "timestamp": r.timestamp.isoformat(),
                        "status": r.status,
                        "latency_ms": r.latency_ms,
                        "success": r.success
                    }
                    for r in results_b
                ]
            },
            "diff": diff,
            "degraded": diff["availability"] < -5 or diff["p95"] > 100
        })
    
    return {
        "snapshot_a": snapshot_a,
        "snapshot_b": snapshot_b,
        "common_targets": sorted(list(common_targets)),
        "comparisons": sorted(comparisons, key=lambda x: x["diff"]["availability"])
    }


@app.get("/api/observers", response_model=List[ObservationPointResponse])
def list_observers(db: Session = Depends(get_db)):
    observers = db.query(ObservationPoint).order_by(ObservationPoint.region, ObservationPoint.name).all()
    return observers


@app.get("/api/observers/{observer_id}", response_model=ObservationPointResponse)
def get_observer(observer_id: int, db: Session = Depends(get_db)):
    observer = db.query(ObservationPoint).filter(ObservationPoint.id == observer_id).first()
    if not observer:
        raise HTTPException(status_code=404, detail="Observer not found")
    return observer


@app.post("/api/observers", response_model=ObservationPointResponse)
def create_observer(observer_create: ObservationPointCreate, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    observer = ObservationPoint(
        name=observer_create.name,
        region=observer_create.region,
        description=observer_create.description,
        status=observer_create.status or "online",
        last_heartbeat=now,
        created_at=now,
        updated_at=now,
    )
    db.add(observer)
    db.commit()
    db.refresh(observer)
    observer_engine._broadcast_observers_update()
    return observer


@app.put("/api/observers/{observer_id}", response_model=ObservationPointResponse)
def update_observer(observer_id: int, observer_update: ObservationPointUpdate, db: Session = Depends(get_db)):
    observer = db.query(ObservationPoint).filter(ObservationPoint.id == observer_id).first()
    if not observer:
        raise HTTPException(status_code=404, detail="Observer not found")

    update_data = observer_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(observer, key, value)
    observer.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(observer)
    observer_engine._broadcast_observers_update()
    return observer


@app.delete("/api/observers/{observer_id}")
def delete_observer(observer_id: int, db: Session = Depends(get_db)):
    observer = db.query(ObservationPoint).filter(ObservationPoint.id == observer_id).first()
    if not observer:
        raise HTTPException(status_code=404, detail="Observer not found")
    db.delete(observer)
    db.commit()
    observer_engine._broadcast_observers_update()
    return {"message": "Observer deleted"}


@app.post("/api/observers/{observer_id}/heartbeat")
def observer_heartbeat(observer_id: int):
    success = observer_engine.heartbeat(observer_id)
    if not success:
        raise HTTPException(status_code=404, detail="Observer not found")
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/observers/{observer_id}/targets")
def get_observer_targets(observer_id: int, db: Session = Depends(get_db)):
    bindings = db.query(TargetObserverBinding).filter(
        TargetObserverBinding.observer_id == observer_id
    ).all()
    target_ids = [b.target_id for b in bindings]
    if not target_ids:
        return []
    targets = db.query(ProbeTarget).filter(ProbeTarget.id.in_(target_ids)).all()
    return [_enrich_target(t, db) for t in targets]


@app.get("/api/targets/{target_id}/observers")
def get_target_observers(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    bindings = db.query(TargetObserverBinding).filter(
        TargetObserverBinding.target_id == target_id
    ).all()
    observer_ids = [b.observer_id for b in bindings]

    if not observer_ids:
        observers = db.query(ObservationPoint).all()
    else:
        observers = db.query(ObservationPoint).filter(ObservationPoint.id.in_(observer_ids)).all()

    return observers


@app.post("/api/targets/{target_id}/observers")
def bind_target_observers(target_id: int, binding: TargetObserverBindingCreate, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    db.query(TargetObserverBinding).filter(TargetObserverBinding.target_id == target_id).delete()

    now = datetime.utcnow()
    for observer_id in binding.observer_ids:
        observer = db.query(ObservationPoint).filter(ObservationPoint.id == observer_id).first()
        if observer:
            db.add(TargetObserverBinding(
                target_id=target_id,
                observer_id=observer_id,
                created_at=now,
            ))

    db.commit()
    return {"message": "Observers bound successfully", "observer_ids": binding.observer_ids}


@app.get("/api/observation-matrix")
def get_observation_matrix(region: str = None):
    return observer_engine.get_matrix_data(region_filter=region)


@app.get("/api/targets/{target_id}/round-history")
def get_target_round_history(target_id: int, limit: int = 20, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    return observer_engine.get_target_round_history(target_id, limit=limit)


@app.get("/api/observers/regions")
def list_observer_regions(db: Session = Depends(get_db)):
    observers = db.query(ObservationPoint).all()
    regions = list({o.region for o in observers})
    regions.sort()
    return {"regions": regions}


def _change_to_response(change: Change, db: Session) -> dict:
    targets = []
    for ct in change.targets:
        target = db.query(ProbeTarget).filter(ProbeTarget.id == ct.target_id).first()
        targets.append({
            "id": ct.id,
            "target_id": ct.target_id,
            "target_name": target.name if target else "",
            "created_at": ct.created_at
        })

    events = []
    for e in sorted(change.events, key=lambda x: x.timestamp, reverse=True):
        events.append({
            "id": e.id,
            "event_type": e.event_type,
            "message": e.message,
            "timestamp": e.timestamp,
            "data": e.data
        })

    return {
        "id": change.id,
        "name": change.name,
        "description": change.description,
        "planned_time": change.planned_time,
        "status": change.status,
        "start_time": change.start_time,
        "end_time": change.end_time,
        "baseline_snapshot_id": change.baseline_snapshot_id,
        "result_snapshot_id": change.result_snapshot_id,
        "conclusion": change.conclusion,
        "conclusion_reason": change.conclusion_reason,
        "notes": change.notes,
        "created_by": change.created_by,
        "created_at": change.created_at,
        "updated_at": change.updated_at,
        "targets": targets,
        "events": events,
        "target_count": len(targets)
    }


def _add_change_event(db: Session, change_id: int, event_type: str, message: str, data: dict = None):
    event = ChangeEvent(
        change_id=change_id,
        event_type=event_type,
        message=message,
        timestamp=datetime.utcnow(),
        data=data
    )
    db.add(event)
    db.flush()
    return event


def _get_change_target_ids(db: Session, change_id: int) -> List[int]:
    bindings = db.query(ChangeTarget).filter(ChangeTarget.change_id == change_id).all()
    return [b.target_id for b in bindings]


def _get_all_affected_target_ids(db: Session, change_id: int) -> List[int]:
    direct_target_ids = _get_change_target_ids(db, change_id)
    all_ids = set(direct_target_ids)

    for tid in direct_target_ids:
        downstream = _get_downstream_targets(db, tid)
        for dt in downstream:
            all_ids.add(dt.id)

    return sorted(list(all_ids))


def _create_snapshot_for_change(db: Session, change: Change, target_ids: List[int], snapshot_name: str) -> Snapshot:
    now = datetime.utcnow()
    start_time = now - timedelta(minutes=10)

    snapshot = Snapshot(
        name=snapshot_name,
        description=f"自动创建 - {change.name}",
        start_time=start_time,
        end_time=now,
        created_at=now
    )
    db.add(snapshot)
    db.flush()

    target_ids_set = set(target_ids)
    results = []
    for tid in target_ids:
        target = db.query(ProbeTarget).filter(ProbeTarget.id == tid).first()
        if not target:
            continue

        probe_results = db.query(ProbeResult).filter(
            ProbeResult.target_id == tid,
            ProbeResult.timestamp >= start_time
        ).order_by(ProbeResult.timestamp.asc()).all()

        for r in probe_results:
            sd = SnapshotData(
                snapshot_id=snapshot.id,
                target_id=tid,
                target_name=target.name,
                timestamp=r.timestamp,
                status=target.status,
                latency_ms=r.latency_ms,
                success=r.success,
                consecutive_failures=target.consecutive_failures,
                consecutive_successes=target.consecutive_successes,
                error_message=r.error_message
            )
            db.add(sd)
            results.append(r)

    alerts = db.query(Alert).filter(
        Alert.target_id.in_(list(target_ids_set)),
        Alert.timestamp >= start_time
    ).all()

    for alert in alerts:
        target = db.query(ProbeTarget).filter(ProbeTarget.id == alert.target_id).first()
        snapshot_alert = SnapshotAlert(
            snapshot_id=snapshot.id,
            target_id=alert.target_id,
            target_name=target.name if target else "",
            timestamp=alert.timestamp,
            from_status=alert.from_status,
            to_status=alert.to_status
        )
        db.add(snapshot_alert)

    snapshot.target_count = len(target_ids)
    snapshot.data_point_count = len(results)

    db.commit()
    db.refresh(snapshot)
    return snapshot


def _analyze_change_conclusion(db: Session, change: Change) -> tuple:
    if not change.baseline_snapshot_id or not change.result_snapshot_id:
        return None, None

    baseline = db.query(Snapshot).filter(Snapshot.id == change.baseline_snapshot_id).first()
    result = db.query(Snapshot).filter(Snapshot.id == change.result_snapshot_id).first()

    if not baseline or not result:
        return None, None

    baseline_data = db.query(SnapshotData).filter(SnapshotData.snapshot_id == baseline.id).all()
    result_data = db.query(SnapshotData).filter(SnapshotData.snapshot_id == result.id).all()

    baseline_by_target = {}
    for d in baseline_data:
        if d.target_name not in baseline_by_target:
            baseline_by_target[d.target_name] = []
        baseline_by_target[d.target_name].append(d)

    result_by_target = {}
    for d in result_data:
        if d.target_name not in result_by_target:
            result_by_target[d.target_name] = []
        result_by_target[d.target_name].append(d)

    common_targets = set(baseline_by_target.keys()) & set(result_by_target.keys())

    degraded_targets = []
    improved_targets = []
    total_availability_drop = 0

    for target_name in common_targets:
        b_data = baseline_by_target[target_name]
        r_data = result_by_target[target_name]

        b_stats = _calculate_stats(b_data)
        r_stats = _calculate_stats(r_data)

        availability_drop = b_stats["availability"] - r_stats["availability"]
        latency_increase = r_stats["p95"] - b_stats["p95"]

        if availability_drop > 10 or latency_increase > 200:
            degraded_targets.append({
                "target_name": target_name,
                "availability_drop": round(availability_drop, 2),
                "latency_increase": round(latency_increase, 2)
            })
        elif availability_drop < -5 or latency_increase < -50:
            improved_targets.append(target_name)

        total_availability_drop += availability_drop

    avg_availability_drop = total_availability_drop / len(common_targets) if common_targets else 0

    if len(degraded_targets) >= 2 or avg_availability_drop > 15:
        conclusion = "rollback"
        reason = f"检测到严重降级: {len(degraded_targets)} 个目标可用性下降超过10%或P95延迟增加超过200ms。建议立即回滚。"
        if degraded_targets:
            reason += " 受影响目标: " + ", ".join([t["target_name"] for t in degraded_targets[:3]])
    elif len(degraded_targets) >= 1 or avg_availability_drop > 5:
        conclusion = "observe"
        reason = f"检测到轻微降级: {len(degraded_targets)} 个目标出现性能下降。建议继续观察并准备回滚预案。"
    else:
        conclusion = "pass"
        reason = "变更通过所有指标检查。"
        if improved_targets:
            reason += f" 有 {len(improved_targets)} 个目标性能有所提升。"

    return conclusion, reason


def _calculate_metrics_for_targets(db: Session, target_ids: List[int], since_time: datetime) -> dict:
    if not target_ids:
        return {"availability": 0, "avg_latency": 0, "p95_latency": 0, "healthy_count": 0, "total": 0}

    results = db.query(ProbeResult).filter(
        ProbeResult.target_id.in_(target_ids),
        ProbeResult.timestamp >= since_time
    ).all()

    if not results:
        return {"availability": 0, "avg_latency": 0, "p95_latency": 0, "healthy_count": 0, "total": len(target_ids)}

    stats = _calculate_stats(results)

    targets = db.query(ProbeTarget).filter(ProbeTarget.id.in_(target_ids)).all()
    healthy_count = sum(1 for t in targets if t.status == "healthy")

    return {
        "availability": round(stats["availability"], 2),
        "avg_latency": round(stats["p50"], 2),
        "p95_latency": round(stats["p95"], 2),
        "p99_latency": round(stats["p99"], 2),
        "healthy_count": healthy_count,
        "total": len(targets),
        "degraded_count": sum(1 for t in targets if t.status == "degraded"),
        "down_count": sum(1 for t in targets if t.status == "down")
    }


def _get_region_divergence(db: Session, target_ids: List[int]) -> List[dict]:
    result = []
    for tid in target_ids:
        target = db.query(ProbeTarget).filter(ProbeTarget.id == tid).first()
        if not target:
            continue

        round_history = observer_engine.get_target_round_history(tid, limit=10)
        if not round_history:
            continue

        latest_round = round_history[0] if round_history else None
        if not latest_round or "results" not in latest_round:
            continue

        regions = {}
        success_by_region = {}
        for r in latest_round["results"]:
            region = r.get("observer_region", "unknown")
            if region not in regions:
                regions[region] = {"success": 0, "total": 0, "latencies": []}
            regions[region]["total"] += 1
            if r.get("success", False):
                regions[region]["success"] += 1
                if r.get("latency_ms"):
                    regions[region]["latencies"].append(r["latency_ms"])

        for region, data in regions.items():
            data["success_rate"] = (data["success"] / data["total"] * 100) if data["total"] > 0 else 0
            if data["latencies"]:
                data["avg_latency"] = sum(data["latencies"]) / len(data["latencies"])
            else:
                data["avg_latency"] = 0

        has_divergence = False
        divergent_regions = []
        success_rates = [r["success_rate"] for r in regions.values()]
        if success_rates:
            rate_range = max(success_rates) - min(success_rates)
            if rate_range > 30:
                has_divergence = True
                for region, data in regions.items():
                    if data["success_rate"] < 70:
                        divergent_regions.append(region)

        result.append({
            "target_id": tid,
            "target_name": target.name,
            "regions": regions,
            "has_divergence": has_divergence,
            "divergent_regions": divergent_regions
        })

    return result


def _init_demo_changes():
    db = next(get_db())
    try:
        change_count = db.query(Change).count()
        if change_count > 0:
            return

        now = datetime.utcnow()
        target1 = db.query(ProbeTarget).filter(ProbeTarget.name.like("%健康%")).first()
        target2 = db.query(ProbeTarget).filter(ProbeTarget.name.like("%间歇%")).first()
        target3 = db.query(ProbeTarget).filter(ProbeTarget.name.like("%API网关%")).first()

        if not target1 or not target2:
            return

        change1 = Change(
            name="核心服务版本 v2.3.1 发布",
            description="用户中心服务版本升级，包含性能优化和Bug修复",
            planned_time=now,
            status="running",
            start_time=now - timedelta(minutes=5),
            notes="灰度发布中，当前50%流量切到新版本",
            created_by="运维团队",
            created_at=now - timedelta(hours=1),
            updated_at=now
        )
        db.add(change1)
        db.flush()

        ct1_1 = ChangeTarget(change_id=change1.id, target_id=target1.id, created_at=now - timedelta(hours=1))
        ct1_2 = ChangeTarget(change_id=change1.id, target_id=target3.id if target3 else target2.id, created_at=now - timedelta(hours=1))
        db.add_all([ct1_1, ct1_2])
        db.flush()

        baseline_snapshot1 = _create_snapshot_for_change(db, change1, [target1.id, target3.id if target3 else target2.id], "基线快照 - 核心服务版本 v2.3.1 发布")
        change1.baseline_snapshot_id = baseline_snapshot1.id
        db.flush()

        _add_change_event(db, change1.id, "created", "变更已创建，等待开始")
        _add_change_event(db, change1.id, "started", "变更已开始，进入守护模式", {"baseline_snapshot_id": baseline_snapshot1.id})
        _add_change_event(db, change1.id, "progress", "灰度发布进度: 50%流量已切换")

        change2 = Change(
            name="数据库配置参数调优",
            description="调整数据库连接池参数和查询超时设置",
            planned_time=now - timedelta(hours=3),
            status="completed",
            start_time=now - timedelta(hours=2, minutes=50),
            end_time=now - timedelta(hours=1, minutes=30),
            conclusion="pass",
            conclusion_reason="变更通过所有指标检查。有 1 个目标性能有所提升。",
            notes="连接池从 100 调整到 200，查询超时从 30s 调整到 15s",
            created_by="DBA团队",
            created_at=now - timedelta(hours=4),
            updated_at=now - timedelta(hours=1, minutes=30)
        )
        db.add(change2)
        db.flush()

        ct2_1 = ChangeTarget(change_id=change2.id, target_id=target2.id, created_at=now - timedelta(hours=4))
        db.add(ct2_1)
        db.flush()

        baseline_snapshot2 = Snapshot(
            name="基线快照 - 数据库配置参数调优",
            description=f"自动创建 - {change2.name}",
            start_time=now - timedelta(hours=3),
            end_time=now - timedelta(hours=2, minutes=50),
            target_count=1,
            data_point_count=15,
            created_at=now - timedelta(hours=2, minutes=50)
        )
        db.add(baseline_snapshot2)
        db.flush()

        result_snapshot2 = Snapshot(
            name="结果快照 - 数据库配置参数调优",
            description=f"自动创建 - {change2.name}",
            start_time=now - timedelta(hours=1, minutes=40),
            end_time=now - timedelta(hours=1, minutes=30),
            target_count=1,
            data_point_count=15,
            created_at=now - timedelta(hours=1, minutes=30)
        )
        db.add(result_snapshot2)
        db.flush()

        for i in range(15):
            t = now - timedelta(hours=3) + timedelta(minutes=i)
            success = i < 10 or i % 3 == 0
            db.add(SnapshotData(
                snapshot_id=baseline_snapshot2.id,
                target_id=target2.id,
                target_name=target2.name,
                timestamp=t,
                status="degraded" if not success else "healthy",
                latency_ms=150 + i * 5 if success else None,
                success=success,
                consecutive_failures=0 if success else 3,
                consecutive_successes=3 if success else 0,
                error_message=None if success else "模拟数据库连接超时"
            ))

        for i in range(15):
            t = now - timedelta(hours=1, minutes=40) + timedelta(minutes=i)
            success = i < 12 or i % 4 == 0
            db.add(SnapshotData(
                snapshot_id=result_snapshot2.id,
                target_id=target2.id,
                target_name=target2.name,
                timestamp=t,
                status="degraded" if not success else "healthy",
                latency_ms=100 + i * 3 if success else None,
                success=success,
                consecutive_failures=0 if success else 2,
                consecutive_successes=5 if success else 0,
                error_message=None if success else "数据库查询超时"
            ))

        db.add(SnapshotAlert(
            snapshot_id=baseline_snapshot2.id,
            target_id=target2.id,
            target_name=target2.name,
            timestamp=now - timedelta(hours=2, minutes=55),
            from_status="healthy",
            to_status="degraded"
        ))

        change2.baseline_snapshot_id = baseline_snapshot2.id
        change2.result_snapshot_id = result_snapshot2.id
        db.flush()

        _add_change_event(db, change2.id, "created", "变更已创建，等待开始", {"planned_time": (now - timedelta(hours=3)).isoformat()})
        _add_change_event(db, change2.id, "started", "变更已开始，进入守护模式", {"baseline_snapshot_id": baseline_snapshot2.id})
        _add_change_event(db, change2.id, "progress", "配置参数已更新，正在观察效果")
        _add_change_event(db, change2.id, "snapshot_created", "结果快照已创建", {"result_snapshot_id": result_snapshot2.id})
        _add_change_event(db, change2.id, "conclusion", "变更结论: 通过", {"conclusion": "pass", "reason": "变更通过所有指标检查。"})
        _add_change_event(db, change2.id, "completed", "变更已完成")

        change3 = Change(
            name="第三方支付网关切换",
            description="将支付网关从供应商A切换到供应商B",
            planned_time=now - timedelta(days=1),
            status="completed",
            start_time=now - timedelta(days=1, hours=2),
            end_time=now - timedelta(days=1, hours=1),
            conclusion="rollback",
            conclusion_reason="检测到严重降级: 1 个目标可用性下降超过10%或P95延迟增加超过200ms。建议立即回滚。受影响目标: 示例服务-间歇故障",
            notes="已回滚到供应商A，正在排查问题",
            created_by="支付团队",
            created_at=now - timedelta(days=1, hours=3),
            updated_at=now - timedelta(days=1)
        )
        db.add(change3)
        db.flush()

        ct3_1 = ChangeTarget(change_id=change3.id, target_id=target2.id, created_at=now - timedelta(days=1, hours=3))
        db.add(ct3_1)
        db.flush()

        baseline_snapshot3 = Snapshot(
            name="基线快照 - 第三方支付网关切换",
            description=f"自动创建 - {change3.name}",
            start_time=now - timedelta(days=1, hours=2, minutes=10),
            end_time=now - timedelta(days=1, hours=2),
            target_count=1,
            data_point_count=20,
            created_at=now - timedelta(days=1, hours=2)
        )
        db.add(baseline_snapshot3)
        db.flush()

        result_snapshot3 = Snapshot(
            name="结果快照 - 第三方支付网关切换",
            description=f"自动创建 - {change3.name}",
            start_time=now - timedelta(days=1, hours=1, minutes=10),
            end_time=now - timedelta(days=1, hours=1),
            target_count=1,
            data_point_count=20,
            created_at=now - timedelta(days=1, hours=1)
        )
        db.add(result_snapshot3)
        db.flush()

        for i in range(20):
            t = now - timedelta(days=1, hours=2, minutes=10) + timedelta(seconds=i * 30)
            success = i % 4 != 0
            db.add(SnapshotData(
                snapshot_id=baseline_snapshot3.id,
                target_id=target2.id,
                target_name=target2.name,
                timestamp=t,
                status="degraded" if not success else "healthy",
                latency_ms=80 + i * 2 if success else None,
                success=success,
                consecutive_failures=0 if success else 1,
                consecutive_successes=3 if success else 0,
                error_message=None if success else "连接超时"
            ))

        for i in range(20):
            t = now - timedelta(days=1, hours=1, minutes=10) + timedelta(seconds=i * 30)
            success = i < 5 or i > 15
            db.add(SnapshotData(
                snapshot_id=result_snapshot3.id,
                target_id=target2.id,
                target_name=target2.name,
                timestamp=t,
                status="down" if not success else "degraded",
                latency_ms=300 + i * 5 if success else None,
                success=success,
                consecutive_failures=0 if success else 8,
                consecutive_successes=1 if success else 0,
                error_message=None if success else "网关无响应"
            ))

        db.add(SnapshotAlert(
            snapshot_id=result_snapshot3.id,
            target_id=target2.id,
            target_name=target2.name,
            timestamp=now - timedelta(days=1, hours=1, minutes=5),
            from_status="degraded",
            to_status="down"
        ))

        change3.baseline_snapshot_id = baseline_snapshot3.id
        change3.result_snapshot_id = result_snapshot3.id
        db.flush()

        _add_change_event(db, change3.id, "created", "变更已创建，等待开始")
        _add_change_event(db, change3.id, "started", "变更已开始，进入守护模式")
        _add_change_event(db, change3.id, "alert", "检测到严重告警: 服务状态变为 down")
        _add_change_event(db, change3.id, "conclusion", "变更结论: 建议回滚", {"conclusion": "rollback"})
        _add_change_event(db, change3.id, "rollback", "已执行回滚操作")
        _add_change_event(db, change3.id, "completed", "变更已完成（已回滚）")

        db.commit()
        print("Demo changes initialized")
    except Exception as e:
        print(f"Demo changes init error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


@app.get("/api/changes", response_model=List[ChangeResponse])
def list_changes(
    status: str = None,
    search: str = "",
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(Change).options(
        joinedload(Change.targets),
        joinedload(Change.events)
    )

    if status:
        query = query.filter(Change.status == status)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Change.name.like(search_pattern)) |
            (Change.description.like(search_pattern))
        )

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            query = query.filter(Change.planned_time >= start_dt)
        except:
            pass

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            query = query.filter(Change.planned_time <= end_dt)
        except:
            pass

    changes = query.order_by(Change.planned_time.desc()).all()
    return [_change_to_response(c, db) for c in changes]


@app.get("/api/changes/active")
def list_active_changes(db: Session = Depends(get_db)):
    changes = db.query(Change).filter(
        Change.status.in_(["pending", "running"])
    ).options(
        joinedload(Change.targets)
    ).order_by(Change.start_time.desc()).all()

    target_changes_map = {}
    for c in changes:
        for ct in c.targets:
            if ct.target_id not in target_changes_map:
                target_changes_map[ct.target_id] = []
            target_changes_map[ct.target_id].append({
                "change_id": c.id,
                "change_name": c.name,
                "change_status": c.status,
                "start_time": c.start_time
            })

    return {
        "changes": [_change_to_response(c, db) for c in changes],
        "target_changes_map": target_changes_map
    }


@app.get("/api/changes/{change_id}", response_model=ChangeResponse)
def get_change(change_id: int, db: Session = Depends(get_db)):
    change = db.query(Change).options(
        joinedload(Change.targets),
        joinedload(Change.events)
    ).filter(Change.id == change_id).first()

    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    return _change_to_response(change, db)


@app.post("/api/changes", response_model=ChangeResponse)
def create_change(change_create: ChangeCreate, db: Session = Depends(get_db)):
    now = datetime.utcnow()

    change = Change(
        name=change_create.name,
        description=change_create.description,
        planned_time=change_create.planned_time,
        status="pending",
        notes=change_create.notes,
        created_by=change_create.created_by,
        created_at=now,
        updated_at=now
    )
    db.add(change)
    db.flush()

    for target_id in change_create.target_ids:
        target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
        if target:
            ct = ChangeTarget(
                change_id=change.id,
                target_id=target_id,
                created_at=now
            )
            db.add(ct)

    db.flush()
    _add_change_event(db, change.id, "created", "变更已创建，等待开始")

    db.commit()
    db.refresh(change)

    manager.broadcast_changes_update()

    return _change_to_response(change, db)


@app.put("/api/changes/{change_id}", response_model=ChangeResponse)
def update_change(change_id: int, change_update: ChangeUpdate, db: Session = Depends(get_db)):
    change = db.query(Change).filter(Change.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    if change.status in ["completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Cannot update a completed or cancelled change")

    now = datetime.utcnow()

    if change_update.name is not None:
        change.name = change_update.name
    if change_update.description is not None:
        change.description = change_update.description
    if change_update.planned_time is not None:
        change.planned_time = change_update.planned_time
    if change_update.notes is not None:
        change.notes = change_update.notes

    if change_update.target_ids is not None and change.status == "pending":
        db.query(ChangeTarget).filter(ChangeTarget.change_id == change_id).delete()
        for target_id in change_update.target_ids:
            target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
            if target:
                ct = ChangeTarget(
                    change_id=change.id,
                    target_id=target_id,
                    created_at=now
                )
                db.add(ct)

    change.updated_at = now
    db.commit()
    db.refresh(change)

    manager.broadcast_changes_update()

    return _change_to_response(change, db)


@app.delete("/api/changes/{change_id}")
def delete_change(change_id: int, db: Session = Depends(get_db)):
    change = db.query(Change).filter(Change.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    if change.status == "running":
        raise HTTPException(status_code=400, detail="Cannot delete a running change. Please end it first.")

    db.delete(change)
    db.commit()

    manager.broadcast_changes_update()

    return {"message": "Change deleted"}


@app.post("/api/changes/{change_id}/start", response_model=ChangeResponse)
def start_change(change_id: int, db: Session = Depends(get_db)):
    change = db.query(Change).filter(Change.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    if change.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot start change with status: {change.status}")

    target_ids = _get_change_target_ids(db, change_id)
    if not target_ids:
        raise HTTPException(status_code=400, detail="No targets specified for this change")

    now = datetime.utcnow()
    change.status = "running"
    change.start_time = now
    change.updated_at = now

    snapshot = _create_snapshot_for_change(db, change, target_ids, f"基线快照 - {change.name}")
    change.baseline_snapshot_id = snapshot.id

    db.flush()
    _add_change_event(db, change.id, "started", "变更已开始，进入守护模式", {
        "baseline_snapshot_id": snapshot.id,
        "target_count": len(target_ids)
    })

    all_affected_ids = _get_all_affected_target_ids(db, change_id)
    _add_change_event(db, change.id, "topology", f"变更影响范围: 直接目标 {len(target_ids)} 个，下游依赖 {len(all_affected_ids) - len(target_ids)} 个", {
        "direct_targets": target_ids,
        "all_affected_targets": all_affected_ids
    })

    db.commit()
    db.refresh(change)

    manager.broadcast_changes_update()

    return _change_to_response(change, db)


@app.post("/api/changes/{change_id}/end", response_model=ChangeResponse)
def end_change(change_id: int, db: Session = Depends(get_db)):
    change = db.query(Change).filter(Change.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    if change.status != "running":
        raise HTTPException(status_code=400, detail=f"Cannot end change with status: {change.status}")

    target_ids = _get_change_target_ids(db, change_id)
    now = datetime.utcnow()
    change.status = "completed"
    change.end_time = now
    change.updated_at = now

    snapshot = _create_snapshot_for_change(db, change, target_ids, f"结果快照 - {change.name}")
    change.result_snapshot_id = snapshot.id

    db.flush()
    _add_change_event(db, change.id, "snapshot_created", "结果快照已创建", {
        "result_snapshot_id": snapshot.id
    })

    conclusion, reason = _analyze_change_conclusion(db, change)
    if conclusion:
        change.conclusion = conclusion
        change.conclusion_reason = reason
        _add_change_event(db, change.id, "conclusion", f"变更结论: {conclusion}", {
            "conclusion": conclusion,
            "reason": reason
        })

    _add_change_event(db, change.id, "completed", "变更已完成")

    db.commit()
    db.refresh(change)

    manager.broadcast_changes_update()

    return _change_to_response(change, db)


@app.post("/api/changes/{change_id}/cancel", response_model=ChangeResponse)
def cancel_change(change_id: int, db: Session = Depends(get_db)):
    change = db.query(Change).filter(Change.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    if change.status not in ["pending", "running"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel change with status: {change.status}")

    now = datetime.utcnow()
    change.status = "cancelled"
    change.end_time = now
    change.updated_at = now

    db.flush()
    _add_change_event(db, change.id, "cancelled", "变更已取消")

    db.commit()
    db.refresh(change)

    manager.broadcast_changes_update()

    return _change_to_response(change, db)


@app.get("/api/changes/{change_id}/observation", response_model=ChangeObservationResponse)
def get_change_observation(change_id: int, db: Session = Depends(get_db)):
    change = db.query(Change).options(
        joinedload(Change.targets),
        joinedload(Change.events)
    ).filter(Change.id == change_id).first()

    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    direct_target_ids = _get_change_target_ids(db, change_id)
    downstream_targets = []
    for tid in direct_target_ids:
        dt_list = _get_downstream_targets(db, tid)
        for dt in dt_list:
            if dt.id not in direct_target_ids and dt.id not in [t.id for t in downstream_targets]:
                downstream_targets.append(dt)

    downstream_target_ids = [t.id for t in downstream_targets]
    all_target_ids = list(set(direct_target_ids + downstream_target_ids))

    direct_targets = db.query(ProbeTarget).filter(ProbeTarget.id.in_(direct_target_ids)).all()
    downstream_targets_full = db.query(ProbeTarget).filter(ProbeTarget.id.in_(downstream_target_ids)).all()

    baseline_time = change.start_time if change.start_time else change.planned_time
    baseline_window_start = baseline_time - timedelta(minutes=10)

    current_time = datetime.utcnow()
    current_window_start = current_time - timedelta(minutes=10)

    baseline_metrics = _calculate_metrics_for_targets(db, all_target_ids, baseline_window_start)
    current_metrics = _calculate_metrics_for_targets(db, all_target_ids, current_window_start)

    status_diff = []
    for tid in all_target_ids:
        target = db.query(ProbeTarget).filter(ProbeTarget.id == tid).first()
        if not target:
            continue

        baseline_result = db.query(ProbeResult).filter(
            ProbeResult.target_id == tid,
            ProbeResult.timestamp >= baseline_window_start
        ).order_by(ProbeResult.timestamp.desc()).first()

        baseline_status = "healthy"
        if baseline_result:
            if not baseline_result.success:
                baseline_status = "degraded"

        current_status = target.status
        status_diff.append({
            "target_id": tid,
            "target_name": target.name,
            "baseline_status": baseline_status,
            "current_status": current_status,
            "status_changed": baseline_status != current_status
        })

    baseline_alerts = db.query(Alert).filter(
        Alert.target_id.in_(all_target_ids),
        Alert.timestamp >= baseline_window_start,
        Alert.timestamp < baseline_time
    ).count()

    current_alerts = db.query(Alert).filter(
        Alert.target_id.in_(all_target_ids),
        Alert.timestamp >= current_window_start
    ).count()

    alerts_since_change = db.query(Alert).filter(
        Alert.target_id.in_(all_target_ids),
        Alert.timestamp >= baseline_time
    ).order_by(Alert.timestamp.desc()).all()

    alert_target_counts = {}
    for a in alerts_since_change:
        if a.target_id not in alert_target_counts:
            target = db.query(ProbeTarget).filter(ProbeTarget.id == a.target_id).first()
            alert_target_counts[a.target_id] = {"name": target.name if target else "", "count": 0}
        alert_target_counts[a.target_id]["count"] += 1

    target_alerts_dict = {}
    for tid, info in alert_target_counts.items():
        target_alerts_dict[info["name"]] = info["count"]

    alerts_timeline = []
    for a in alerts_since_change:
        target = db.query(ProbeTarget).filter(ProbeTarget.id == a.target_id).first()
        alerts_timeline.append({
            "id": a.id,
            "target_id": a.target_id,
            "target_name": target.name if target else "",
            "timestamp": a.timestamp,
            "from_status": a.from_status,
            "to_status": a.to_status,
            "acknowledged": a.acknowledged
        })

    region_divergence = _get_region_divergence(db, direct_target_ids)

    comparison_result = None
    if change.baseline_snapshot_id and change.result_snapshot_id:
        comparison_res = compare_snapshots_internal(db, change.baseline_snapshot_id, change.result_snapshot_id)
        comparison_result = comparison_res

    change_response = _change_to_response(change, db)

    return {
        "change": change_response,
        "target_ids": direct_target_ids,
        "target_names": [t.name for t in direct_targets],
        "downstream_target_ids": downstream_target_ids,
        "downstream_target_names": [t.name for t in downstream_targets_full],
        "all_target_ids": all_target_ids,
        "status_diff": status_diff,
        "alert_stats": {
            "baseline_count": baseline_alerts,
            "current_count": current_alerts,
            "new_alerts": len(alerts_since_change),
            "resolved_alerts": max(0, baseline_alerts - current_alerts),
            "target_alerts": target_alerts_dict
        },
        "region_divergence": region_divergence,
        "baseline_metrics": baseline_metrics,
        "current_metrics": current_metrics,
        "alerts_timeline": alerts_timeline,
        "comparison_result": comparison_result
    }


@app.get("/api/changes/{change_id}/comparison", response_model=ChangeComparisonResponse)
def get_change_comparison(change_id: int, db: Session = Depends(get_db)):
    change = db.query(Change).filter(Change.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    baseline_snapshot = None
    result_snapshot = None

    if change.baseline_snapshot_id:
        baseline_snapshot = db.query(Snapshot).filter(Snapshot.id == change.baseline_snapshot_id).first()
    if change.result_snapshot_id:
        result_snapshot = db.query(Snapshot).filter(Snapshot.id == change.result_snapshot_id).first()

    if not baseline_snapshot or not result_snapshot:
        return {
            "baseline_snapshot": baseline_snapshot,
            "result_snapshot": result_snapshot,
            "target_comparisons": [],
            "overall_summary": {"message": "快照数据不完整，无法进行对比"},
            "conclusion": change.conclusion,
            "conclusion_reason": change.conclusion_reason
        }

    comparison_data = compare_snapshots_internal(db, change.baseline_snapshot_id, change.result_snapshot_id)

    degraded_count = sum(1 for c in comparison_data["comparisons"] if c.get("degraded", False))
    improved_count = sum(1 for c in comparison_data["comparisons"] if c["diff"]["availability"] > 0)
    total_targets = len(comparison_data["common_targets"])

    summary = {
        "total_targets": total_targets,
        "degraded_count": degraded_count,
        "improved_count": improved_count,
        "unchanged_count": total_targets - degraded_count - improved_count,
        "avg_availability_change": sum(c["diff"]["availability"] for c in comparison_data["comparisons"]) / total_targets if total_targets > 0 else 0,
        "avg_p95_change": sum(c["diff"]["p95"] for c in comparison_data["comparisons"]) / total_targets if total_targets > 0 else 0
    }

    return {
        "baseline_snapshot": baseline_snapshot,
        "result_snapshot": result_snapshot,
        "target_comparisons": comparison_data["comparisons"],
        "overall_summary": summary,
        "conclusion": change.conclusion,
        "conclusion_reason": change.conclusion_reason
    }


def compare_snapshots_internal(db: Session, snapshot_a_id: int, snapshot_b_id: int) -> dict:
    snapshot_a = db.query(Snapshot).filter(Snapshot.id == snapshot_a_id).first()
    snapshot_b = db.query(Snapshot).filter(Snapshot.id == snapshot_b_id).first()

    if not snapshot_a or not snapshot_b:
        return {"common_targets": [], "comparisons": []}

    data_a = db.query(SnapshotData).filter(SnapshotData.snapshot_id == snapshot_a_id).all()
    data_b = db.query(SnapshotData).filter(SnapshotData.snapshot_id == snapshot_b_id).all()

    targets_a = {}
    targets_b = {}

    for d in data_a:
        if d.target_name not in targets_a:
            targets_a[d.target_name] = []
        targets_a[d.target_name].append(d)

    for d in data_b:
        if d.target_name not in targets_b:
            targets_b[d.target_name] = []
        targets_b[d.target_name].append(d)

    common_targets = set(targets_a.keys()) & set(targets_b.keys())

    comparisons = []
    for target_name in common_targets:
        results_a = targets_a[target_name]
        results_b = targets_b[target_name]

        stats_a = _calculate_stats(results_a)
        stats_b = _calculate_stats(results_b)

        diff = {
            "availability": stats_b["availability"] - stats_a["availability"],
            "p50": stats_b["p50"] - stats_a["p50"],
            "p95": stats_b["p95"] - stats_a["p95"],
            "p99": stats_b["p99"] - stats_a["p99"],
        }

        comparisons.append({
            "target_name": target_name,
            "snapshot_a": {
                "stats": stats_a,
                "data_points": len(results_a)
            },
            "snapshot_b": {
                "stats": stats_b,
                "data_points": len(results_b)
            },
            "diff": diff,
            "degraded": diff["availability"] < -5 or diff["p95"] > 100
        })

    return {
        "common_targets": sorted(list(common_targets)),
        "comparisons": sorted(comparisons, key=lambda x: x["diff"]["availability"])
    }


@app.get("/api/targets/{target_id}/active-changes", response_model=List[TargetActiveChange])
def get_target_active_changes(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    changes = db.query(Change).join(ChangeTarget).filter(
        ChangeTarget.target_id == target_id,
        Change.status.in_(["pending", "running"])
    ).order_by(Change.start_time.desc()).all()

    result = []
    for c in changes:
        result.append({
            "change_id": c.id,
            "change_name": c.name,
            "change_status": c.status,
            "start_time": c.start_time
        })

    return result


@app.get("/api/changes/{change_id}/topology")
def get_change_topology(change_id: int, db: Session = Depends(get_db)):
    change = db.query(Change).filter(Change.id == change_id).first()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    direct_target_ids = _get_change_target_ids(db, change_id)
    all_affected_ids = _get_all_affected_target_ids(db, change_id)

    targets = db.query(ProbeTarget).filter(ProbeTarget.id.in_(all_affected_ids)).all()
    dependencies = db.query(Dependency).filter(
        (Dependency.upstream_id.in_(all_affected_ids)) |
        (Dependency.downstream_id.in_(all_affected_ids))
    ).all()

    target_map = {}
    for t in targets:
        target_map[t.id] = {
            "id": t.id,
            "name": t.name,
            "status": t.status,
            "type": t.type,
            "is_direct": t.id in direct_target_ids,
            "is_downstream": t.id not in direct_target_ids
        }

    deps_data = []
    for d in dependencies:
        if d.upstream_id in target_map and d.downstream_id in target_map:
            deps_data.append({
                "id": d.id,
                "upstream_id": d.upstream_id,
                "downstream_id": d.downstream_id,
                "description": d.description
            })

    return {
        "change_id": change_id,
        "change_name": change.name,
        "change_status": change.status,
        "targets": list(target_map.values()),
        "dependencies": deps_data,
        "direct_target_count": len(direct_target_ids),
        "downstream_target_count": len(all_affected_ids) - len(direct_target_ids)
    }


def _get_slo_target_ids(slo: SLOTarget, db: Session) -> List[int]:
    ids = set()
    if slo.target_id:
        ids.add(slo.target_id)
    if slo.group_id:
        targets = db.query(ProbeTarget).filter(ProbeTarget.group_id == slo.group_id).all()
        for t in targets:
            ids.add(t.id)
    return list(ids)


def _calculate_budget_for_slo(slo: SLOTarget, db: Session) -> dict:
    now = datetime.utcnow()
    window_start = now - timedelta(days=slo.window_days)
    total_budget = 100.0 - slo.slo_target

    latest_snap = db.query(SLOBudgetSnapshot).filter(
        SLOBudgetSnapshot.slo_id == slo.id
    ).order_by(SLOBudgetSnapshot.timestamp.desc()).first()

    if latest_snap:
        recent_snaps = db.query(SLOBudgetSnapshot).filter(
            SLOBudgetSnapshot.slo_id == slo.id,
            SLOBudgetSnapshot.timestamp >= now - timedelta(hours=6)
        ).order_by(SLOBudgetSnapshot.timestamp.asc()).all()

        if len(recent_snaps) >= 2:
            first = recent_snaps[0]
            last = recent_snaps[-1]
            hours_diff = (last.timestamp - first.timestamp).total_seconds() / 3600
            if hours_diff > 0:
                consumed_diff = last.budget_consumed - first.budget_consumed
                burn_rate = consumed_diff / hours_diff * 24 / total_budget if total_budget > 0 else 0
            else:
                burn_rate = 0
        else:
            burn_rate = 0

        budget_remaining_pct = (latest_snap.budget_remaining / total_budget * 100) if total_budget > 0 else 100.0

        if budget_remaining_pct <= 0:
            status = "breached"
        elif budget_remaining_pct <= 20:
            status = "critical"
        elif budget_remaining_pct <= 50:
            status = "fast_burn"
        else:
            status = "safe"

        attribution = {
            "service_fault": latest_snap.service_fault,
            "regional_anomaly": latest_snap.regional_anomaly,
            "dependency_cascade": latest_snap.dependency_cascade,
            "change_induced": latest_snap.change_induced,
        }

        return {
            "current_value": latest_snap.current_value,
            "total_budget": round(total_budget, 4),
            "budget_consumed": latest_snap.budget_consumed,
            "budget_remaining": latest_snap.budget_remaining,
            "budget_remaining_pct": round(budget_remaining_pct, 2),
            "burn_rate": round(burn_rate, 4),
            "status": status,
            "attribution": attribution,
        }

    target_ids = _get_slo_target_ids(slo, db)

    if not target_ids:
        return {
            "current_value": 100.0,
            "total_budget": 100.0 - slo.slo_target,
            "budget_consumed": 0,
            "budget_remaining": 100.0 - slo.slo_target,
            "budget_remaining_pct": 100.0,
            "burn_rate": 0,
            "status": "safe",
            "attribution": {"service_fault": 0, "regional_anomaly": 0, "dependency_cascade": 0, "change_induced": 0},
        }

    results = db.query(ProbeResult).filter(
        ProbeResult.target_id.in_(target_ids),
        ProbeResult.timestamp >= window_start
    ).order_by(ProbeResult.timestamp.asc()).all()

    observer_results = db.query(ObserverProbeResult).filter(
        ObserverProbeResult.target_id.in_(target_ids),
        ObserverProbeResult.timestamp >= window_start
    ).all()

    total = len(results) + len(observer_results)
    if total == 0:
        return {
            "current_value": 100.0,
            "total_budget": 100.0 - slo.slo_target,
            "budget_consumed": 0,
            "budget_remaining": 100.0 - slo.slo_target,
            "budget_remaining_pct": 100.0,
            "burn_rate": 0,
            "status": "safe",
            "attribution": {"service_fault": 0, "regional_anomaly": 0, "dependency_cascade": 0, "change_induced": 0},
        }

    all_results = list(results) + list(observer_results)
    failed = [r for r in all_results if not r.success]
    success_count = total - len(failed)
    current_value = (success_count / total) * 100

    total_budget = 100.0 - slo.slo_target
    budget_consumed = max(0, total_budget - (current_value - slo.slo_target))
    if current_value >= 100.0:
        budget_consumed = 0
    elif current_value < slo.slo_target:
        budget_consumed = total_budget
    else:
        budget_consumed = total_budget - (current_value - slo.slo_target)

    budget_remaining = total_budget - budget_consumed
    budget_remaining_pct = (budget_remaining / total_budget * 100) if total_budget > 0 else 100.0

    service_fault = 0
    regional_anomaly = 0
    dependency_cascade = 0
    change_induced = 0

    for r in failed:
        is_cascade = False
        is_change = False
        is_regional = False

        if hasattr(r, 'target_id') and r.target_id:
            target = db.query(ProbeTarget).filter(ProbeTarget.id == r.target_id).first()
            if target and target.cascade_affected:
                is_cascade = True
            changes_for_target = db.query(ChangeTarget).filter(ChangeTarget.target_id == r.target_id).all()
            for ct in changes_for_target:
                ch = db.query(Change).filter(Change.id == ct.change_id).first()
                if ch and ch.status == "running" and ch.start_time:
                    if r.timestamp >= ch.start_time:
                        is_change = True
                        break

        if isinstance(r, ObserverProbeResult) and r.observer_id:
            obs = db.query(ObservationPoint).filter(ObservationPoint.id == r.observer_id).first()
            if obs:
                region_results_for_target = [or2 for or2 in observer_results
                                              if or2.observer_id == r.observer_id
                                              and or2.target_id == r.target_id]
                region_failed = sum(1 for x in region_results_for_target if not x.success)
                region_total = len(region_results_for_target)
                if region_total > 0:
                    region_fail_rate = region_failed / region_total
                    overall_fail_rate = len(failed) / total if total > 0 else 0
                    if region_fail_rate > overall_fail_rate * 1.5:
                        is_regional = True

        if is_cascade and is_change:
            dependency_cascade += 0.5
            change_induced += 0.5
        elif is_cascade:
            dependency_cascade += 1
        elif is_change:
            change_induced += 1
        elif is_regional:
            regional_anomaly += 1
        else:
            service_fault += 1

    total_attrib = service_fault + regional_anomaly + dependency_cascade + change_induced
    if total_attrib > 0 and total_attrib != len(failed):
        scale = len(failed) / total_attrib
        service_fault *= scale
        regional_anomaly *= scale
        dependency_cascade *= scale
        change_induced *= scale

    attribution = {
        "service_fault": round(service_fault, 2),
        "regional_anomaly": round(regional_anomaly, 2),
        "dependency_cascade": round(dependency_cascade, 2),
        "change_induced": round(change_induced, 2),
    }

    recent_window = now - timedelta(hours=6)
    recent_results = [r for r in all_results if r.timestamp >= recent_window]
    if recent_results:
        recent_failed = sum(1 for r in recent_results if not r.success)
        recent_rate = recent_failed / len(recent_results)
        burn_rate = recent_rate * 24
    else:
        burn_rate = 0

    if budget_remaining_pct <= 0:
        status = "breached"
    elif budget_remaining_pct <= 20:
        status = "critical"
    elif budget_remaining_pct <= 50:
        status = "fast_burn"
    else:
        status = "safe"

    return {
        "current_value": round(current_value, 4),
        "total_budget": round(total_budget, 4),
        "budget_consumed": round(budget_consumed, 4),
        "budget_remaining": round(budget_remaining, 4),
        "budget_remaining_pct": round(budget_remaining_pct, 2),
        "burn_rate": round(burn_rate, 4),
        "status": status,
        "attribution": attribution,
    }


def _build_budget_timeline(slo: SLOTarget, db: Session) -> List[dict]:
    now = datetime.utcnow()
    points = []
    total_budget = 100.0 - slo.slo_target

    snapshots = db.query(SLOBudgetSnapshot).filter(
        SLOBudgetSnapshot.slo_id == slo.id
    ).order_by(SLOBudgetSnapshot.timestamp.asc()).all()

    if snapshots:
        for snap in snapshots:
            points.append({
                "timestamp": snap.timestamp,
                "total_budget": snap.total_budget,
                "budget_consumed": snap.budget_consumed,
                "budget_remaining": snap.budget_remaining,
                "current_value": snap.current_value,
                "attribution": {
                    "service_fault": snap.service_fault,
                    "regional_anomaly": snap.regional_anomaly,
                    "dependency_cascade": snap.dependency_cascade,
                    "change_induced": snap.change_induced,
                },
            })
        return points

    num_points = 30
    for i in range(num_points, -1, -1):
        point_time = now - timedelta(days=slo.window_days * i / num_points)
        window_start = point_time - timedelta(days=slo.window_days)
        target_ids = _get_slo_target_ids(slo, db)
        if not target_ids:
            continue

        results = db.query(ProbeResult).filter(
            ProbeResult.target_id.in_(target_ids),
            ProbeResult.timestamp >= window_start,
            ProbeResult.timestamp < point_time
        ).all()

        observer_results = db.query(ObserverProbeResult).filter(
            ObserverProbeResult.target_id.in_(target_ids),
            ObserverProbeResult.timestamp >= window_start,
            ObserverProbeResult.timestamp < point_time
        ).all()

        total = len(results) + len(observer_results)
        if total == 0:
            continue

        all_res = list(results) + list(observer_results)
        success_count = sum(1 for r in all_res if r.success)
        current_value = (success_count / total) * 100
        budget_consumed = max(0, total_budget - (current_value - slo.slo_target)) if current_value < 100.0 else 0
        budget_remaining = max(0, total_budget - budget_consumed)

        points.append({
            "timestamp": point_time,
            "total_budget": round(total_budget, 4),
            "budget_consumed": round(budget_consumed, 4),
            "budget_remaining": round(budget_remaining, 4),
            "current_value": round(current_value, 4),
            "attribution": {"service_fault": 0, "regional_anomaly": 0, "dependency_cascade": 0, "change_induced": 0},
        })

    return points


def _slo_to_response(slo: SLOTarget, db: Session) -> dict:
    target_name = None
    group_name = None
    if slo.target_id:
        t = db.query(ProbeTarget).filter(ProbeTarget.id == slo.target_id).first()
        if t:
            target_name = t.name
    if slo.group_id:
        g = db.query(ProbeGroup).filter(ProbeGroup.id == slo.group_id).first()
        if g:
            group_name = g.name
    return {
        "id": slo.id,
        "name": slo.name,
        "description": slo.description,
        "target_id": slo.target_id,
        "target_name": target_name,
        "group_id": slo.group_id,
        "group_name": group_name,
        "slo_type": slo.slo_type,
        "slo_target": slo.slo_target,
        "latency_threshold_ms": slo.latency_threshold_ms,
        "window_days": slo.window_days,
        "created_at": slo.created_at,
        "updated_at": slo.updated_at,
    }


@app.get("/api/slo", response_model=List[SLOTargetResponse])
def list_slo_targets(db: Session = Depends(get_db)):
    slos = db.query(SLOTarget).order_by(SLOTarget.id.asc()).all()
    return [_slo_to_response(s, db) for s in slos]


@app.get("/api/slo/budget/overview", response_model=List[SLOBudgetOverviewItem])
def get_slo_budget_overview(db: Session = Depends(get_db)):
    slos = db.query(SLOTarget).order_by(SLOTarget.id.asc()).all()
    result = []
    for slo in slos:
        budget = _calculate_budget_for_slo(slo, db)
        target_name = None
        group_name = None
        if slo.target_id:
            t = db.query(ProbeTarget).filter(ProbeTarget.id == slo.target_id).first()
            if t:
                target_name = t.name
        if slo.group_id:
            g = db.query(ProbeGroup).filter(ProbeGroup.id == slo.group_id).first()
            if g:
                group_name = g.name
        result.append({
            "slo_id": slo.id,
            "slo_name": slo.name,
            "slo_type": slo.slo_type,
            "slo_target": slo.slo_target,
            "current_value": budget["current_value"],
            "budget_remaining_pct": budget["budget_remaining_pct"],
            "burn_rate": budget["burn_rate"],
            "status": budget["status"],
            "target_name": target_name,
            "group_name": group_name,
        })
    return result


@app.post("/api/slo", response_model=SLOTargetResponse)
def create_slo_target(slo_create: SLOTargetCreate, db: Session = Depends(get_db)):
    now = datetime.utcnow()
    slo = SLOTarget(
        name=slo_create.name,
        description=slo_create.description,
        target_id=slo_create.target_id,
        group_id=slo_create.group_id,
        slo_type=slo_create.slo_type,
        slo_target=slo_create.slo_target,
        latency_threshold_ms=slo_create.latency_threshold_ms,
        window_days=slo_create.window_days,
        created_at=now,
        updated_at=now,
    )
    db.add(slo)
    db.commit()
    db.refresh(slo)
    return _slo_to_response(slo, db)


@app.get("/api/slo/{slo_id}", response_model=SLOTargetResponse)
def get_slo_target(slo_id: int, db: Session = Depends(get_db)):
    slo = db.query(SLOTarget).filter(SLOTarget.id == slo_id).first()
    if not slo:
        raise HTTPException(status_code=404, detail="SLO target not found")
    return _slo_to_response(slo, db)


@app.put("/api/slo/{slo_id}", response_model=SLOTargetResponse)
def update_slo_target(slo_id: int, slo_update: SLOTargetUpdate, db: Session = Depends(get_db)):
    slo = db.query(SLOTarget).filter(SLOTarget.id == slo_id).first()
    if not slo:
        raise HTTPException(status_code=404, detail="SLO target not found")
    update_data = slo_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(slo, key, value)
    slo.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(slo)
    return _slo_to_response(slo, db)


@app.delete("/api/slo/{slo_id}")
def delete_slo_target(slo_id: int, db: Session = Depends(get_db)):
    slo = db.query(SLOTarget).filter(SLOTarget.id == slo_id).first()
    if not slo:
        raise HTTPException(status_code=404, detail="SLO target not found")
    db.query(SLOBudgetSnapshot).filter(SLOBudgetSnapshot.slo_id == slo_id).delete()
    db.delete(slo)
    db.commit()
    return {"message": "SLO target deleted"}


@app.get("/api/slo/{slo_id}/budget", response_model=SLOBudgetResponse)
def get_slo_budget(slo_id: int, db: Session = Depends(get_db)):
    slo = db.query(SLOTarget).filter(SLOTarget.id == slo_id).first()
    if not slo:
        raise HTTPException(status_code=404, detail="SLO target not found")
    budget = _calculate_budget_for_slo(slo, db)
    timeline = _build_budget_timeline(slo, db)
    return {
        "slo_id": slo.id,
        "slo_name": slo.name,
        "slo_type": slo.slo_type,
        "slo_target": slo.slo_target,
        "window_days": slo.window_days,
        "current_value": budget["current_value"],
        "total_budget": budget["total_budget"],
        "budget_consumed": budget["budget_consumed"],
        "budget_remaining": budget["budget_remaining"],
        "budget_remaining_pct": budget["budget_remaining_pct"],
        "burn_rate": budget["burn_rate"],
        "status": budget["status"],
        "attribution": budget["attribution"],
        "timeline": timeline,
    }


@app.get("/api/slo/{slo_id}/prediction", response_model=SLOPredictionResponse)
def get_slo_prediction(slo_id: int, db: Session = Depends(get_db)):
    slo = db.query(SLOTarget).filter(SLOTarget.id == slo_id).first()
    if not slo:
        raise HTTPException(status_code=404, detail="SLO target not found")
    budget = _calculate_budget_for_slo(slo, db)
    burn_rate = budget["burn_rate"]
    total_budget = budget["total_budget"]
    budget_remaining = budget["budget_remaining"]
    current_value = budget["current_value"]

    hours_to_breach = None
    predicted_breach_time = None
    will_breach_24h = False

    if burn_rate > 0 and budget_remaining > 0:
        hours_to_breach = budget_remaining / (burn_rate * total_budget / (slo.window_days * 24)) if burn_rate * total_budget > 0 else None
        if hours_to_breach:
            predicted_breach_time = datetime.utcnow() + timedelta(hours=hours_to_breach)
            will_breach_24h = hours_to_breach <= 24
    elif budget_remaining <= 0:
        hours_to_breach = 0
        predicted_breach_time = datetime.utcnow()
        will_breach_24h = True

    projected_24h_drop = burn_rate * (24 / (slo.window_days * 24)) * total_budget if total_budget > 0 else 0
    projected_value_24h = max(0, current_value - projected_24h_drop)

    return {
        "slo_id": slo.id,
        "slo_name": slo.name,
        "current_value": current_value,
        "burn_rate": burn_rate,
        "hours_to_breach": round(hours_to_breach, 2) if hours_to_breach else None,
        "predicted_breach_time": predicted_breach_time,
        "projected_value_24h": round(projected_value_24h, 4),
        "will_breach_24h": will_breach_24h,
    }


@app.get("/api/incidents", response_model=IncidentListResponse)
def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Incident).options(
        joinedload(Incident.targets),
        joinedload(Incident.alerts),
        joinedload(Incident.timeline),
        joinedload(Incident.notes),
    )

    if status:
        query = query.filter(Incident.status == status)
    if severity:
        query = query.filter(Incident.severity == severity)

    incidents = query.order_by(Incident.created_at.desc()).all()

    active_count = db.query(Incident).filter(Incident.status.in_(["active", "recovering"])).count()
    review_count = db.query(Incident).filter(Incident.status == "recovering", Incident.needs_review == True).count()
    resolved_count = db.query(Incident).filter(Incident.status == "resolved").count()

    return {
        "items": [_incident_to_response(i, db) for i in incidents],
        "active_count": active_count,
        "review_count": review_count,
        "resolved_count": resolved_count,
    }


@app.get("/api/incidents/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    incident = db.query(Incident).options(
        joinedload(Incident.targets),
        joinedload(Incident.alerts),
        joinedload(Incident.timeline),
        joinedload(Incident.notes),
    ).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _incident_to_response(incident, db, include_details=True)


@app.patch("/api/incidents/{incident_id}", response_model=IncidentResponse)
def update_incident(incident_id: int, payload: IncidentUpdate, db: Session = Depends(get_db)):
    incident = db.query(Incident).options(
        joinedload(Incident.targets),
        joinedload(Incident.alerts),
        joinedload(Incident.timeline),
        joinedload(Incident.notes),
    ).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    data = payload.dict(exclude_unset=True)

    if "status" in data:
        old_status = incident.status
        new_status = data["status"]
        if old_status != new_status:
            db.add(IncidentTimeline(
                incident_id=incident.id,
                event_type="status_change",
                title=f"状态变更: {old_status} → {new_status}",
                severity="info",
            ))

    if "severity" in data:
        old_sev = incident.severity
        new_sev = data["severity"]
        if old_sev != new_sev:
            db.add(IncidentTimeline(
                incident_id=incident.id,
                event_type="severity_change",
                title=f"严重等级变更: {old_sev} → {new_sev}",
                severity="warning",
            ))

    if "owner" in data and data["owner"] != incident.owner:
        db.add(IncidentTimeline(
            incident_id=incident.id,
            event_type="owner_transfer",
            title=f"负责人变更: {incident.owner or '未指派'} → {data['owner']}",
            severity="info",
        ))

    if "mitigated" in data and data["mitigated"] != incident.mitigated:
        if data["mitigated"]:
            incident.mitigated_at = datetime.utcnow()
            db.add(IncidentTimeline(
                incident_id=incident.id,
                event_type="mitigation",
                title="已标记止血",
                description="当前故障已临时止血，正在等待完全恢复",
                severity="info",
            ))
        else:
            incident.mitigated_at = None
            db.add(IncidentTimeline(
                incident_id=incident.id,
                event_type="mitigation",
                title="取消止血标记",
                severity="warning",
            ))

    for key, value in data.items():
        setattr(incident, key, value)

    incident.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(incident)

    manager.broadcast_incidents_update()
    return _incident_to_response(incident, db, include_details=True)


@app.post("/api/incidents/{incident_id}/acknowledge", response_model=IncidentResponse)
def acknowledge_incident(incident_id: int, payload: IncidentAcknowledge, db: Session = Depends(get_db)):
    incident = db.query(Incident).options(
        joinedload(Incident.targets),
        joinedload(Incident.alerts),
        joinedload(Incident.timeline),
        joinedload(Incident.notes),
    ).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    now = datetime.utcnow()
    incident.acknowledged = True
    incident.acknowledged_at = now
    incident.acknowledged_by = payload.acknowledged_by
    if not incident.owner:
        incident.owner = payload.acknowledged_by

    db.add(IncidentTimeline(
        incident_id=incident.id,
        event_type="acknowledged",
        title=f"{payload.acknowledged_by} 手动接管故障",
        description=payload.notes if payload.notes else None,
        severity="info",
        timestamp=now,
    ))

    incident.updated_at = now
    db.commit()
    db.refresh(incident)

    manager.broadcast_incidents_update()
    return _incident_to_response(incident, db, include_details=True)


@app.post("/api/incidents/{incident_id}/transfer", response_model=IncidentResponse)
def transfer_incident(incident_id: int, payload: IncidentTransfer, db: Session = Depends(get_db)):
    incident = db.query(Incident).options(
        joinedload(Incident.targets),
        joinedload(Incident.alerts),
        joinedload(Incident.timeline),
        joinedload(Incident.notes),
    ).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    now = datetime.utcnow()
    old_owner = incident.owner or "未指派"
    incident.owner = payload.new_owner
    incident.updated_at = now

    db.add(IncidentTimeline(
        incident_id=incident.id,
        event_type="owner_transfer",
        title=f"转交负责人: {old_owner} → {payload.new_owner}",
        description=payload.notes if payload.notes else None,
        severity="info",
        timestamp=now,
    ))

    if payload.notes:
        db.add(IncidentNote(
            incident_id=incident.id,
            author=payload.transferred_by or "system",
            content=payload.notes,
            action_type="transfer",
        ))

    db.commit()
    db.refresh(incident)

    manager.broadcast_incidents_update()
    return _incident_to_response(incident, db, include_details=True)


@app.post("/api/incidents/{incident_id}/notes", response_model=IncidentResponse)
def add_incident_note(incident_id: int, payload: IncidentNoteCreate, db: Session = Depends(get_db)):
    incident = db.query(Incident).options(
        joinedload(Incident.targets),
        joinedload(Incident.alerts),
        joinedload(Incident.timeline),
        joinedload(Incident.notes),
    ).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    note = IncidentNote(
        incident_id=incident.id,
        author=payload.author,
        content=payload.content,
        action_type=payload.action_type or "note",
    )
    db.add(note)

    db.add(IncidentTimeline(
        incident_id=incident.id,
        event_type="note_added",
        title=f"{payload.author} 添加了处置记录",
        description=payload.content[:200],
        severity="info",
    ))

    incident.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(incident)

    manager.broadcast_incidents_update()
    return _incident_to_response(incident, db, include_details=True)


@app.post("/api/incidents/{incident_id}/resolve", response_model=IncidentResponse)
def resolve_incident(incident_id: int, payload: IncidentResolve, db: Session = Depends(get_db)):
    incident = db.query(Incident).options(
        joinedload(Incident.targets),
        joinedload(Incident.alerts),
        joinedload(Incident.timeline),
        joinedload(Incident.notes),
    ).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    now = datetime.utcnow()
    incident.status = "resolved"
    incident.recovered_at = now
    incident.bleed_over_until = None
    if payload.mark_for_review:
        incident.needs_review = True
        if payload.review_notes:
            incident.review_notes = payload.review_notes

    db.add(IncidentTimeline(
        incident_id=incident.id,
        event_type="status_change",
        title="故障已解决",
        description=f"由 {payload.resolved_by} 确认解决" + (f"：{payload.review_notes}" if payload.review_notes else ""),
        severity="info",
        timestamp=now,
    ))

    incident.updated_at = now
    db.commit()
    db.refresh(incident)

    manager.broadcast_incidents_update()
    return _incident_to_response(incident, db, include_details=True)


def _source_to_response(source: RegistrySource, db: Session) -> dict:
    group_name = None
    if source.default_group_id:
        group = db.query(ProbeGroup).filter(ProbeGroup.id == source.default_group_id).first()
        if group:
            group_name = group.name

    target_count = db.query(ProbeTarget).filter(ProbeTarget.source_id == source.id).count()

    return {
        "id": source.id,
        "name": source.name,
        "url": source.url,
        "pull_interval": source.pull_interval,
        "default_group_id": source.default_group_id,
        "default_group_name": group_name,
        "default_type": source.default_type,
        "default_interval": source.default_interval,
        "default_timeout": source.default_timeout,
        "deprecate_after_hours": source.deprecate_after_hours,
        "enabled": source.enabled,
        "last_sync_at": source.last_sync_at,
        "last_sync_status": source.last_sync_status,
        "headers": source.headers,
        "target_count": target_count,
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


def _sync_event_to_response(event: SyncEvent, db: Session, include_details: bool = False) -> dict:
    source_name = None
    if event.source:
        source_name = event.source.name
    else:
        src = db.query(RegistrySource).filter(RegistrySource.id == event.source_id).first()
        if src:
            source_name = src.name

    details = []
    if include_details:
        for d in event.details:
            target_name = None
            if d.target_id:
                t = db.query(ProbeTarget).filter(ProbeTarget.id == d.target_id).first()
                if t:
                    target_name = t.name
            details.append({
                "id": d.id,
                "target_id": d.target_id,
                "target_name": target_name,
                "service_name": d.service_name,
                "service_address": d.service_address,
                "action": d.action,
                "detail": d.detail,
                "created_at": d.created_at,
            })

    return {
        "id": event.id,
        "source_id": event.source_id,
        "source_name": source_name,
        "triggered_by": event.triggered_by,
        "status": event.status,
        "started_at": event.started_at,
        "finished_at": event.finished_at,
        "discovered_count": event.discovered_count,
        "new_count": event.new_count,
        "deprecated_count": event.deprecated_count,
        "failed_count": event.failed_count,
        "unchanged_count": event.unchanged_count,
        "error_message": event.error_message,
        "raw_service_count": event.raw_service_count,
        "details": details,
    }


@app.get("/api/registry-sources", response_model=List[RegistrySourceResponse])
def list_registry_sources(db: Session = Depends(get_db)):
    sources = db.query(RegistrySource).all()
    return [_source_to_response(s, db) for s in sources]


@app.get("/api/registry-sources/{source_id}", response_model=RegistrySourceResponse)
def get_registry_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(RegistrySource).filter(RegistrySource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Registry source not found")
    return _source_to_response(source, db)


@app.post("/api/registry-sources", response_model=RegistrySourceResponse)
def create_registry_source(source_data: RegistrySourceCreate, db: Session = Depends(get_db)):
    source = RegistrySource(**source_data.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    sync_engine.add_source(source.id)
    return _source_to_response(source, db)


@app.put("/api/registry-sources/{source_id}", response_model=RegistrySourceResponse)
def update_registry_source(source_id: int, source_update: RegistrySourceUpdate, db: Session = Depends(get_db)):
    source = db.query(RegistrySource).filter(RegistrySource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Registry source not found")

    update_data = source_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(source, key, value)

    db.commit()
    db.refresh(source)
    sync_engine.update_source(source.id)
    return _source_to_response(source, db)


@app.delete("/api/registry-sources/{source_id}")
def delete_registry_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(RegistrySource).filter(RegistrySource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Registry source not found")

    sync_engine.remove_source(source_id)
    db.delete(source)
    db.commit()
    return {"message": "Registry source deleted"}


@app.post("/api/registry-sources/{source_id}/sync")
async def trigger_sync(source_id: int):
    result = await sync_engine.sync_source(source_id, triggered_by="manual")
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.get("/api/registry-sources/{source_id}/sync-events", response_model=SyncEventListResponse)
def list_sync_events(source_id: int, limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    source = db.query(RegistrySource).filter(RegistrySource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Registry source not found")

    total = db.query(SyncEvent).filter(SyncEvent.source_id == source_id).count()
    events = db.query(SyncEvent).filter(
        SyncEvent.source_id == source_id
    ).order_by(SyncEvent.started_at.desc()).offset(offset).limit(limit).all()

    return {
        "items": [_sync_event_to_response(e, db, include_details=False) for e in events],
        "total": total,
    }


@app.get("/api/sync-events/{event_id}", response_model=SyncEventResponse)
def get_sync_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(SyncEvent).filter(SyncEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Sync event not found")
    return _sync_event_to_response(event, db, include_details=True)


@app.get("/api/sync-events", response_model=SyncEventListResponse)
def list_all_sync_events(limit: int = 20, offset: int = 0, db: Session = Depends(get_db)):
    total = db.query(SyncEvent).count()
    events = db.query(SyncEvent).order_by(
        SyncEvent.started_at.desc()
    ).offset(offset).limit(limit).all()

    return {
        "items": [_sync_event_to_response(e, db, include_details=False) for e in events],
        "total": total,
    }


@app.post("/api/targets/{target_id}/restore")
def restore_target(target_id: int, db: Session = Depends(get_db)):
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    if not target.deprecated:
        raise HTTPException(status_code=400, detail="Target is not deprecated")

    result = sync_engine.restore_target(target_id)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    db.expire_all()
    target = db.query(ProbeTarget).filter(ProbeTarget.id == target_id).first()
    return _enrich_target(target, db)


class StartRecordingRequest(BaseModel):
    name: str
    description: Optional[str] = None
    tags: Optional[TypingList[str]] = None
    filter_target_ids: Optional[TypingList[int]] = None
    filter_group_ids: Optional[TypingList[int]] = None
    created_by: Optional[str] = None


class UpdateRecordingRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[TypingList[str]] = None


class StartPlaybackRequest(BaseModel):
    session_id: int
    speed: Optional[float] = 1.0


class SetSpeedRequest(BaseModel):
    speed: float


class SeekRequest(BaseModel):
    index: int


@app.get("/api/recording/status")
def get_recording_status():
    return recording_engine.get_recording_status()


@app.post("/api/recording/start")
def start_recording(req: StartRecordingRequest):
    result = recording_engine.start_recording(
        name=req.name,
        description=req.description,
        filter_target_ids=req.filter_target_ids,
        filter_group_ids=req.filter_group_ids,
        tags=req.tags,
        created_by=req.created_by,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/recording/stop")
def stop_recording():
    result = recording_engine.stop_recording()
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/recording/sessions")
def list_recording_sessions(skip: int = 0, limit: int = 50):
    return recording_engine.list_sessions(skip=skip, limit=limit)


@app.get("/api/recording/sessions/{session_id}")
def get_recording_session(session_id: int):
    result = recording_engine.get_session_detail(session_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.put("/api/recording/sessions/{session_id}")
def update_recording_session(session_id: int, req: UpdateRecordingRequest):
    result = recording_engine.update_session(
        session_id=session_id,
        name=req.name,
        description=req.description,
        tags=req.tags,
    )
    if "error" in result:
        raise HTTPException(status_code=400 if "不存在" not in result["error"] else 404, detail=result["error"])
    return result


@app.delete("/api/recording/sessions/{session_id}")
def delete_recording_session(session_id: int):
    result = recording_engine.delete_session(session_id)
    if "error" in result:
        raise HTTPException(status_code=400 if "不存在" not in result["error"] else 404, detail=result["error"])
    return result


@app.get("/api/playback/status")
def get_playback_status():
    return playback_engine.get_playback_status()


@app.post("/api/playback/start")
def start_playback(req: StartPlaybackRequest):
    result = playback_engine.start_playback(
        session_id=req.session_id,
        speed=req.speed,
    )
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/playback/pause")
def pause_playback():
    result = playback_engine.pause_playback()
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/playback/resume")
def resume_playback():
    result = playback_engine.resume_playback()
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/playback/stop")
def stop_playback(restore: bool = True):
    result = playback_engine.stop_playback(restore=restore)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/playback/speed")
def set_playback_speed(req: SetSpeedRequest):
    result = playback_engine.set_speed(req.speed)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/playback/seek")
def playback_seek(req: SeekRequest):
    result = playback_engine.seek_to(req.index)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

