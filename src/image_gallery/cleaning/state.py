import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class OperatorRunState:
    """单个算子的运行摘要。"""

    operator_name: str
    config_hash: str
    status: str
    parameter_columns: list[str]
    evaluation_columns: list[str]
    processed_count: int
    skipped_count: int
    failed_count: int
    message: str | None = None


@dataclass(frozen=True)
class CleanerRunState:
    """一次 Cleaner 运行的状态快照。"""

    run_id: str
    dataset_fingerprint: str
    cleaner_type: str
    enabled_operator_configs: list[dict[str, dict[str, object]]]
    operator_config_hashes: dict[str, str]
    parameter_config_hashes: dict[str, str]
    parameter_table_path: str
    evaluation_table_path: str
    operator_outputs_path: str
    parameter_manifest_path: str
    relation_paths: dict[str, str]
    artifact_paths: dict[str, str]
    started_at: str
    finished_at: str
    status: str
    operator_states: list[OperatorRunState]


class JsonRunStateStore:
    """基于 state.json 的最小运行状态存储。"""

    def load(self, path: str | Path) -> CleanerRunState:
        """读取状态文件。"""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        operator_states = [OperatorRunState(**item) for item in payload["operator_states"]]
        return CleanerRunState(
            run_id=payload["run_id"],
            dataset_fingerprint=payload["dataset_fingerprint"],
            cleaner_type=payload["cleaner_type"],
            enabled_operator_configs=payload["enabled_operator_configs"],
            operator_config_hashes=payload["operator_config_hashes"],
            parameter_config_hashes=payload.get("parameter_config_hashes", {}),
            parameter_table_path=payload["parameter_table_path"],
            evaluation_table_path=payload["evaluation_table_path"],
            operator_outputs_path=payload["operator_outputs_path"],
            parameter_manifest_path=payload.get("parameter_manifest_path", ""),
            relation_paths=payload.get("relation_paths", {}),
            artifact_paths=payload["artifact_paths"],
            started_at=payload.get("started_at", ""),
            finished_at=payload.get("finished_at", ""),
            status=payload["status"],
            operator_states=operator_states,
        )

    def save(self, state: CleanerRunState, path: str | Path) -> None:
        """原子写入状态文件。"""
        state_path = Path(path)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = state_path.with_name(f"{state_path.name}.tmp")
        temporary_path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary_path.replace(state_path)


def build_state_frame(state: CleanerRunState) -> pd.DataFrame:
    """把 operator_states 转成 state() 可打印的 DataFrame。"""
    rows = [
        {
            "operator_name": operator_state.operator_name,
            "status": operator_state.status,
            "processed_count": operator_state.processed_count,
            "skipped_count": operator_state.skipped_count,
            "failed_count": operator_state.failed_count,
            "message": operator_state.message,
        }
        for operator_state in state.operator_states
    ]
    return pd.DataFrame(
        rows,
        columns=["operator_name", "status", "processed_count", "skipped_count", "failed_count", "message"],
    )
