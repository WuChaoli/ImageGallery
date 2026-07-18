"""CleanerResult 使用的运行产物读取边界。"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pandas as pd

from image_gallery.cleaning.context import CleanerRunPaths
from image_gallery.cleaning.state import JsonRunStateStore
from image_gallery.cleaning.tables import initialize_evaluation_table


def read_status(cache_root: Path, run_id: str) -> str:
    """读取 `run_state.sqlite` 中的运行状态。"""
    database_path = Path(cache_root) / run_id / "run_state.sqlite"
    if not database_path.exists():
        return "running"

    connection = sqlite3.connect(database_path)
    try:
        row = connection.execute(
            "SELECT status FROM cleaning_run WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return "running"
        return str(row[0])
    finally:
        connection.close()


def read_json_or_empty(
    path: Path,
    default: dict[str, object] | list[object],
) -> dict[str, object] | list[object]:
    """读取 JSON 文件；文件不存在时返回默认值。"""
    if not path.exists():
        return default
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return cast(dict[str, object], raw)
    if isinstance(raw, list):
        return cast(list[object], raw)
    return default


def ensure_str_list(values: list[object], *, context: str) -> list[str]:
    """按上下文过滤并校验 JSON 列表值。"""
    normalized: list[str] = []
    for value in values:
        if isinstance(value, str):
            normalized.append(value)
        else:
            raise TypeError(f"invalid {context}: {value!r}")
    return normalized


@dataclass(frozen=True)
class ResultArtifacts:
    """集中定位并读取一次清洗运行的持久化产物。"""

    cache_root: Path
    run_id: str

    def run_dir(self) -> Path:
        """返回本次运行目录。"""
        return self.cache_root / self.run_id

    def table_file(self, filename: str) -> Path:
        """返回存在的运行表文件。"""
        table_path = self.run_dir() / "tables" / filename
        if table_path.exists():
            return table_path
        raise FileNotFoundError(f"table file not found: {filename}")

    def run_paths(self) -> CleanerRunPaths:
        """拼装本次运行的路径集合。"""
        run_dir = self.run_dir()
        return CleanerRunPaths(
            run_dir=run_dir,
            parameter_table_path=self.table_file("parameter_table.parquet"),
            evaluation_table_path=self.table_file("evaluation_table.parquet"),
            operator_outputs_path=run_dir / "manifests" / "operator_outputs.json",
            parameter_manifest_path=run_dir / "manifests" / "parameter_manifest.json",
            relations_dir=run_dir / "relations",
            artifacts_dir=run_dir / "artifacts",
            manifests_dir=run_dir / "manifests",
            state_path=run_dir / "state.json",
        )

    def load_operator_outputs(self) -> dict[str, list[str]]:
        """读取 operator outputs，并保留缺失文件回退。"""
        raw_outputs = read_json_or_empty(self.run_paths().operator_outputs_path, default={})
        if not isinstance(raw_outputs, dict):
            return {}
        parsed: dict[str, list[str]] = {}
        for operator_name, columns in raw_outputs.items():
            if not isinstance(columns, list):
                continue
            parsed[str(operator_name)] = ensure_str_list(
                columns,
                context="operator_outputs columns",
            )
        return parsed

    def load_parameter_manifest(self) -> dict[str, dict[str, object]]:
        """读取 parameter manifest，并保留缺失文件回退。"""
        raw_manifest = read_json_or_empty(self.run_paths().parameter_manifest_path, default={})
        if not isinstance(raw_manifest, dict):
            return {}
        parsed: dict[str, dict[str, object]] = {}
        for parameter_name, value in raw_manifest.items():
            if isinstance(value, dict):
                parsed[str(parameter_name)] = value
        return parsed

    def load_parameter_table(self) -> pd.DataFrame:
        """加载 parameter table，不存在时返回最小骨架。"""
        path = self.run_paths().parameter_table_path
        if path.exists():
            return pd.read_parquet(path)
        return pd.DataFrame(
            {
                "image_id": pd.Series(dtype="string"),
                "image_uri": pd.Series(dtype="string"),
            }
        )

    def load_evaluation_table(self) -> pd.DataFrame:
        """加载 evaluation table，不存在时从参数表初始化。"""
        path = self.run_paths().evaluation_table_path
        if path.exists():
            return pd.read_parquet(path)
        return initialize_evaluation_table(self.load_parameter_table())

    def load_relation_names(self) -> list[str]:
        """优先从 state.json 读取 relation 名称。"""
        state_path = self.run_paths().state_path
        if not state_path.exists():
            return []
        state = JsonRunStateStore().load(state_path)
        return sorted(state.relation_paths)
