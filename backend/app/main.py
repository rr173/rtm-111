from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from typing import List, Set
from datetime import datetime, timedelta
from collections import deque

from .database import engine, get_db, Base
from .models import (
    ProbeTarget, ProbeResult, Alert, ProbeGroup, Dependency,
    ProbeRule, ProbeRuleVersion, ProbeRuleStep,
    ProbeRuleExecution, ProbeRuleStepExecution,
    Snapshot, SnapshotData, SnapshotAlert,
    ObservationPoint, TargetObserverBinding, ObserverProbeResult,
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
)
from .observer_engine import observer_engine
from .probe_engine import probe_engine
from .websocket_manager import manager, get_target_history


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
    loop = asyncio.get_running_loop()
    probe_engine.set_loop(loop)
    manager.set_loop(loop)
    observer_engine.set_loop(loop)
    _init_demo_data()
    _init_demo_rules()
    _init_demo_observers()
    await observer_engine.start()
    await probe_engine.start()


@app.on_event("shutdown")
async def shutdown_event():
    await observer_engine.stop()
    await probe_engine.stop()


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
        if observer_count > 0:
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
