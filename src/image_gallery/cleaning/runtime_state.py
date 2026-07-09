"""SQLite runtime-state persistence for cleaner execution."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from image_gallery.cleaning.events import RuntimeEvent
from image_gallery.cleaning.graph import CleaningStateGraph, GraphNode


@dataclass(frozen=True)
class RunRecord:
    """一次清洗运行的最小运行时元数据快照。"""

    run_id: str
    cleaner_type: str
    status: str
    dataset_fingerprint: str
    plan_hash: str
    label: str
    tags: list[str]
    sample_size: int | None
    sample_rule: dict[str, Any] | None


@runtime_checkable
class EventLike(Protocol):
    """用于 event-style 对象兼容接入。"""

    event_type: Any
    run_id: str
    node_id: str | None
    message: str | None
    payload: dict[str, Any] | None
    timestamp: str | None


class SQLiteRunStateStore:
    """面向单次运行的 SQLite 状态存储。"""

    _DATABASE_NAME = "run_state.sqlite"

    def __init__(self, connection: sqlite3.Connection, run_dir: Path, run_record: RunRecord) -> None:
        self._connection = connection
        self._run_dir = run_dir
        self._run_record = run_record
        self._connection.row_factory = sqlite3.Row

    @classmethod
    def initialize(cls, run_dir: Path, run_record: RunRecord) -> SQLiteRunStateStore:
        """初始化数据库并写入运行记录，返回可复用状态存储实例。"""
        run_directory = Path(run_dir)
        run_directory.mkdir(parents=True, exist_ok=True)
        db_path = run_directory / cls._DATABASE_NAME
        connection = sqlite3.connect(db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        _create_schema(connection)
        store = cls(connection=connection, run_dir=run_directory, run_record=run_record)
        store._upsert_run_record(run_record)
        return store

    def close(self) -> None:
        """关闭数据库连接。"""
        self._connection.close()

    def load_run(self, run_id: str) -> RunRecord:
        """读取当前运行元信息。"""
        row = self._connection.execute(
            """
            SELECT
                run_id,
                cleaner_type,
                status,
                dataset_fingerprint,
                plan_hash,
                label,
                tags_json,
                sample_size,
                sample_rule_json
            FROM cleaning_run
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"run not found: {run_id}")

        return RunRecord(
            run_id=row["run_id"],
            cleaner_type=row["cleaner_type"],
            status=row["status"],
            dataset_fingerprint=row["dataset_fingerprint"],
            plan_hash=row["plan_hash"],
            label=row["label"],
            tags=_loads_json(row["tags_json"], default=[]),
            sample_size=row["sample_size"],
            sample_rule=_loads_json(row["sample_rule_json"]),
        )

    def record_graph(self, graph: CleaningStateGraph) -> None:
        """把 `CleaningStateGraph` 持久化到 `graph_node` 表。"""
        for node in graph.nodes:
            self.record_graph_node(node)

    def record_graph_node(self, node: GraphNode) -> None:
        """更新单个图节点元信息。"""
        self._connection.execute(
            """
            INSERT INTO graph_node (
                run_id,
                node_id,
                node_type,
                operator_name,
                computer_name,
                stage_name,
                execution_mode,
                required_parameters_json,
                produced_parameters_json,
                config_hash,
                policy_hash,
                upstream_node_ids_json,
                checkpoint_strategy,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, node_id) DO UPDATE SET
                node_type = excluded.node_type,
                operator_name = excluded.operator_name,
                computer_name = excluded.computer_name,
                stage_name = excluded.stage_name,
                execution_mode = excluded.execution_mode,
                required_parameters_json = excluded.required_parameters_json,
                produced_parameters_json = excluded.produced_parameters_json,
                config_hash = excluded.config_hash,
                policy_hash = excluded.policy_hash,
                upstream_node_ids_json = excluded.upstream_node_ids_json,
                checkpoint_strategy = excluded.checkpoint_strategy,
                status = excluded.status
            """,
            (
                self._run_record.run_id,
                node.node_id,
                node.node_type,
                node.operator_name,
                node.computer_name,
                node.stage_name,
                _value_or_none(node.execution_mode.value if node.execution_mode else None),
                json.dumps(sorted(node.required_parameters)),
                json.dumps(sorted(node.produced_parameters)),
                node.config_hash,
                node.policy_hash,
                json.dumps(node.upstream_node_ids),
                node.checkpoint_strategy,
                "pending",
            ),
        )
        self._connection.commit()

    def update_run_status(self, run_id: str, status: str) -> None:
        """更新运行状态。"""
        self._connection.execute(
            """
            UPDATE cleaning_run
            SET status = ?
            WHERE run_id = ?
            """,
            (status, run_id),
        )
        self._connection.commit()

    def record_node_started(self, node_id: str) -> None:
        """将节点标记为开始运行。"""
        now = _utcnow()
        self._connection.execute(
            """
            INSERT INTO graph_node (
                run_id,
                node_id,
                node_type,
                operator_name,
                computer_name,
                stage_name,
                execution_mode,
                required_parameters_json,
                produced_parameters_json,
                config_hash,
                policy_hash,
                upstream_node_ids_json,
                checkpoint_strategy,
                status,
                started_at
            )
            VALUES (?, ?, "", "", "", "", "", "[]", "[]", "", "", "[]", "", "running", ?)
            ON CONFLICT(run_id, node_id) DO UPDATE SET
                status = excluded.status,
                started_at = excluded.started_at
            """,
            (self._run_record.run_id, node_id, now),
        )
        self._connection.commit()

    def record_event(
        self,
        event: RuntimeEvent | str,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """记录运行时事件。"""
        record = self._coerce_event(event, message=message, payload=payload)
        self._connection.execute(
            """
            INSERT INTO run_event (run_id, event_type, node_id, message, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                self._run_record.run_id,
                record.event_type,
                record.node_id,
                record.message,
                json.dumps(record.payload or {}),
                _utcnow(),
            ),
        )
        self._connection.commit()

    def list_events(self, run_id: str) -> list[RuntimeEvent]:
        """按写入顺序返回事件列表。"""
        if run_id != self._run_record.run_id:
            raise KeyError(f"run not found: {run_id}")
        rows = self._connection.execute(
            """
            SELECT event_type, node_id, message, payload_json
            FROM run_event
            WHERE run_id = ?
            ORDER BY id
            """,
            (run_id,),
        ).fetchall()
        return [
            RuntimeEvent(
                event_type=row["event_type"],
                run_id=run_id,
                node_id=row["node_id"],
                message=row["message"],
                payload=_loads_json(row["payload_json"], default={}),
            )
            for row in rows
        ]

    def _upsert_run_record(self, run_record: RunRecord) -> None:
        """把运行主记录持久化。"""
        self._connection.execute(
            """
            INSERT INTO cleaning_run (
                run_id,
                cleaner_type,
                status,
                dataset_fingerprint,
                plan_hash,
                label,
                tags_json,
                sample_size,
                sample_rule_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                cleaner_type = excluded.cleaner_type,
                status = excluded.status,
                dataset_fingerprint = excluded.dataset_fingerprint,
                plan_hash = excluded.plan_hash,
                label = excluded.label,
                tags_json = excluded.tags_json,
                sample_size = excluded.sample_size,
                sample_rule_json = excluded.sample_rule_json
            """,
            (
                run_record.run_id,
                run_record.cleaner_type,
                run_record.status,
                run_record.dataset_fingerprint,
                run_record.plan_hash,
                run_record.label,
                json.dumps(run_record.tags),
                run_record.sample_size,
                json.dumps(run_record.sample_rule) if run_record.sample_rule is not None else None,
            ),
        )
        self._connection.commit()

    def _coerce_event(
        self,
        event: RuntimeEvent | str,
        *,
        message: str | None,
        payload: dict[str, Any] | None,
    ) -> RuntimeEvent:
        """兼容字符串调用与未来 RuntimeEvent 对象调用。"""
        if isinstance(event, str):
            return RuntimeEvent(
                event_type=event,
                run_id=self._run_record.run_id,
                message=message,
                payload=payload,
                timestamp=_utcnow(),
            )
        if isinstance(event, RuntimeEvent):
            return RuntimeEvent(
                event_type=event.event_type,
                run_id=event.run_id,
                node_id=event.node_id,
                message=message if message is not None else event.message,
                payload=payload if payload is not None else (event.payload or {}),
                timestamp=event.timestamp or _utcnow(),
            )

        if isinstance(event, EventLike):
            return RuntimeEvent(
                event_type=str(event.event_type),
                run_id=event.run_id,
                node_id=event.node_id,
                message=message if message is not None else event.message,
                payload=payload if payload is not None else _ensure_dict(event.payload),
                timestamp=_optional_str(event.timestamp) or _utcnow(),
            )

        raise TypeError(f"unsupported event type: {type(event)!r}")


def _create_schema(connection: sqlite3.Connection) -> None:
    """创建 runtime state 所需的 SQLite 表。"""
    statements = [
        """
        CREATE TABLE IF NOT EXISTS cleaning_run (
            run_id TEXT PRIMARY KEY,
            cleaner_type TEXT NOT NULL,
            status TEXT NOT NULL,
            dataset_fingerprint TEXT NOT NULL,
            plan_hash TEXT NOT NULL,
            label TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            sample_size INTEGER,
            sample_rule_json TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS graph_node (
            run_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            node_type TEXT NOT NULL,
            operator_name TEXT,
            computer_name TEXT,
            stage_name TEXT,
            execution_mode TEXT,
            required_parameters_json TEXT NOT NULL,
            produced_parameters_json TEXT NOT NULL,
            config_hash TEXT NOT NULL,
            policy_hash TEXT NOT NULL,
            upstream_node_ids_json TEXT NOT NULL,
            checkpoint_strategy TEXT NOT NULL,
            status TEXT,
            started_at TEXT,
            finished_at TEXT,
            message TEXT,
            PRIMARY KEY (run_id, node_id),
            FOREIGN KEY (run_id) REFERENCES cleaning_run(run_id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS stage_run (
            run_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            stage_name TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            payload_json TEXT,
            message TEXT,
            PRIMARY KEY (run_id, node_id, stage_name),
            FOREIGN KEY (run_id, node_id) REFERENCES graph_node(run_id, node_id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS batch_run (
            run_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            stage_name TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            payload_json TEXT,
            message TEXT,
            PRIMARY KEY (run_id, node_id, stage_name, batch_id),
            FOREIGN KEY (run_id, node_id) REFERENCES graph_node(run_id, node_id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS artifact (
            run_id TEXT NOT NULL,
            artifact_id TEXT NOT NULL,
            artifact_type TEXT NOT NULL,
            owner_node_id TEXT NOT NULL,
            schema_version INTEGER,
            schema_hash TEXT,
            config_hash TEXT,
            policy_hash TEXT,
            row_count INTEGER,
            part_files_json TEXT,
            checksum TEXT,
            created_at TEXT,
            commit_marker TEXT,
            manifest_uri TEXT,
            PRIMARY KEY (run_id, artifact_id),
            FOREIGN KEY (run_id) REFERENCES cleaning_run(run_id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS run_event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            node_id TEXT,
            message TEXT,
            payload_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES cleaning_run(run_id) ON DELETE CASCADE
        )
        """,
    ]
    for statement in statements:
        connection.execute(statement)
    connection.commit()


def _utcnow() -> str:
    """返回带 UTC 时区的 ISO 时间字符串。"""
    return datetime.now(timezone.utc).isoformat()


def _loads_json(raw: str | None, *, default: Any = None) -> Any:
    """将文本 JSON 安全反序列化为 Python 对象。"""
    if raw is None:
        return default
    if raw == "":
        return default
    return json.loads(raw)


def _ensure_dict(value: object) -> dict[str, Any]:
    """把事件 payload 规整为字典。"""
    return value if isinstance(value, dict) else {}


def _optional_str(value: object) -> str | None:
    """将可空对象转换为可空字符串。"""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _value_or_none(value: Any) -> str:
    """将可空值安全转成字符串或空。"""
    if value is None:
        return ""
    return str(value)
