"""Cleaner 运行结果对象及导出、预览、解释能力。"""

from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pandas as pd

from image_gallery.cleaning.context import CleanerRunPaths
from image_gallery.cleaning.export import export_cleaning_result
from image_gallery.cleaning.html_preview import PreviewHtmlOptions, write_preview_html
from image_gallery.cleaning.preview import PreviewResult, build_preview
from image_gallery.cleaning.preview_policy import PreviewPolicy, resolve_preview_policy
from image_gallery.cleaning.state import JsonRunStateStore, build_state_frame
from image_gallery.cleaning.tables import CleaningTables, initialize_evaluation_table
from image_gallery.dataset import Dataset
from image_gallery.operators.builtin import create_default_registry


def read_result_status(cache_root: Path, run_id: str) -> str:
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


def _read_json_or_empty(path: Path, default: dict[str, object] | list[object]) -> dict[str, object] | list[object]:
    """读取 JSON 文件；文件不存在时返回默认值。"""
    if not path.exists():
        return default
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return cast(dict[str, object], raw)
    if isinstance(raw, list):
        return cast(list[object], raw)
    return default


def _normalize_value(value: object) -> object:
    """将 Pandas 的缺失值转为空字符串，便于 HTML/JSON 输出。"""
    if pd.isna(value):
        return ""
    return value


def _deduplicate_columns(columns: list[str]) -> list[str]:
    """去重并保留列顺序。"""
    seen: set[str] = set()
    deduplicated: list[str] = []
    for column in columns:
        if column in seen:
            continue
        seen.add(column)
        deduplicated.append(column)
    return deduplicated


def _ensure_str_list(values: list[object], *, context: str) -> list[str]:
    """按上下文过滤并校验 JSON 列表值。"""
    normalized: list[str] = []
    for value in values:
        if isinstance(value, str):
            normalized.append(value)
        else:
            raise ValueError(f"invalid {context}: {value!r}")
    return normalized


@dataclass(frozen=True)
class CleanerResult:
    """清洗一次运行后的只读结果入口。"""

    run_id: str
    _cache_root: Path

    def __init__(self, run_id: str, cache_root: Path) -> None:
        """构造函数。"""
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "_cache_root", Path(cache_root))

    def _run_dir(self) -> Path:
        """返回本次运行目录。"""
        return self._cache_root / self.run_id

    def _table_file(self, filename: str) -> Path:
        """按新约定和兼容路径返回表文件。"""
        table_path = self._run_dir() / "tables" / filename
        legacy_path = self._run_dir() / filename
        if table_path.exists():
            return table_path
        if legacy_path.exists():
            return legacy_path
        raise FileNotFoundError(f"table file not found: {filename}")

    def _run_paths(self) -> CleanerRunPaths:
        """拼装本次运行的路径集合。"""
        run_dir = self._run_dir()
        return CleanerRunPaths(
            run_dir=run_dir,
            parameter_table_path=self._table_file("parameter_table.parquet"),
            evaluation_table_path=self._table_file("evaluation_table.parquet"),
            operator_outputs_path=run_dir / "operator_outputs.yaml",
            parameter_manifest_path=run_dir / "parameter_manifest.json",
            relations_dir=run_dir / "relations",
            artifacts_dir=run_dir / "artifacts",
            state_path=run_dir / "state.json",
        )

    def _load_operator_outputs(self) -> dict[str, list[str]]:
        """读取 operator_outputs.json（兼容文件不存在）。"""
        raw_outputs = _read_json_or_empty(self._run_paths().operator_outputs_path, default={})
        if not isinstance(raw_outputs, dict):
            return {}
        parsed: dict[str, list[str]] = {}
        for operator_name, columns in raw_outputs.items():
            if not isinstance(columns, list):
                continue
            parsed[str(operator_name)] = _ensure_str_list(
                columns,
                context="operator_outputs columns",
            )
        return parsed

    def _load_parameter_manifest(self) -> dict[str, dict[str, object]]:
        """读取 parameter_manifest.json（兼容文件不存在）。"""
        raw_manifest = _read_json_or_empty(self._run_paths().parameter_manifest_path, default={})
        if not isinstance(raw_manifest, dict):
            return {}
        parsed: dict[str, dict[str, object]] = {}
        for parameter_name, value in raw_manifest.items():
            if not isinstance(value, dict):
                continue
            parsed[str(parameter_name)] = value
        return parsed

    def _load_parameter_table(self) -> pd.DataFrame:
        """按文件加载 parameter_table，不存在时给出最小骨架。"""
        path = self._run_paths().parameter_table_path
        if path.exists():
            return pd.read_parquet(path)
        return pd.DataFrame({"image_id": pd.Series(dtype="string"), "image_uri": pd.Series(dtype="string")})

    def _load_evaluation_table(self) -> pd.DataFrame:
        """按文件加载 evaluation_table，不存在时用参数表补齐。"""
        path = self._run_paths().evaluation_table_path
        if path.exists():
            return pd.read_parquet(path)
        return initialize_evaluation_table(self._load_parameter_table())

    def _load_relation_names(self) -> list[str]:
        """优先从 state.json 读取 relation 名称。"""
        state_path = self._run_paths().state_path
        if not state_path.exists():
            return []
        state = JsonRunStateStore().load(state_path)
        return sorted(state.relation_paths.keys())

    def status(self) -> str:
        """返回运行状态。"""
        return read_result_status(self._cache_root, self.run_id)

    def export_table(self, kind: str, path: Path | str) -> Path:
        """把某张运行表拷贝到目标路径。"""
        kind_map = {
            "parameter": "parameter_table.parquet",
            "parameters": "parameter_table.parquet",
            "evaluation": "evaluation_table.parquet",
            "evaluations": "evaluation_table.parquet",
            "full": "evaluation_table.parquet",
        }
        normalized = kind.strip().lower()
        if normalized not in kind_map:
            raise ValueError(f"unsupported export_table kind: {kind}")
        source = self._table_file(kind_map[normalized])
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return destination

    def export_manifest(self, path: Path | str) -> Path:
        """导出 operator_outputs + parameter_manifest 到给定路径。"""
        destination = Path(path)
        payload = {
            "operator_outputs": self._load_operator_outputs(),
            "parameter_manifest": self._load_parameter_manifest(),
        }
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return destination

    def export(self, kind: str, path: Path | str) -> Dataset:
        """按 kind 导出清洗产物并返回 Dataset。"""
        tables = CleaningTables(
            parameter_table=self._load_parameter_table(),
            evaluation_table=self._load_evaluation_table(),
            operator_outputs=self._load_operator_outputs(),
            parameter_manifest=self._load_parameter_manifest(),
        )
        export_cleaning_result(
            kind=str(kind).strip().lower(),
            tables=tables,
            output_path=str(path),
        )
        return Dataset.from_path(str(path))

    def preview(self, limit: int = 20) -> PreviewResult:
        """返回 preview 概览。"""
        return build_preview(
            evaluation_table=self._load_evaluation_table(),
            operator_outputs=self._load_operator_outputs(),
            limit=limit,
        )

    def _preview_policy(self, operator_name: str | None) -> PreviewPolicy:
        """按算子名读取 preview 策略，缺省则回退默认策略。"""
        if operator_name is None:
            return PreviewPolicy()
        try:
            return create_default_registry().get_operator(operator_name).preview_policy
        except Exception:
            return PreviewPolicy()

    def preview_html(
        self,
        path: Path | str,
        *,
        operator_name: str | None = None,
        actions: str | list[str] | tuple[str, ...] | None = None,
        filters: dict[str, object] | None = None,
        groupby: str | None = None,
        include_group_context: bool | None = None,
        sort_by: list[str] | None = None,
        ascending: bool | list[bool] = True,
        caption_columns: list[str] | None = None,
        max_rows: int = 200,
        max_groups: int = 50,
        max_items_per_group: int = 20,
        thumbnail_size: int = 320,
        columns_per_row: int = 6,
        action: str | None = None,
    ) -> Path:
        """把预览结果渲染到 HTML。"""
        requested_actions = actions
        if requested_actions is None and action is not None:
            requested_actions = action

        operator_outputs = self._load_operator_outputs()
        evaluation_table = self._load_evaluation_table()
        policy = self._preview_policy(operator_name)
        action_column: str | None = None
        if operator_name is not None and operator_name not in operator_outputs:
            raise KeyError(f"unknown operator_name: {operator_name}")
        if operator_name is not None:
            selected = operator_outputs[operator_name]
            action_columns = [column for column in selected if column.endswith("_action")]
            if not action_columns:
                raise ValueError(f"operator has no action column: {operator_name}")
            action_column = action_columns[0]
            keep_columns = _deduplicate_columns(["image_id", "image_uri", "final_action", action_column] + selected)
            for required in keep_columns:
                if required not in evaluation_table.columns:
                    raise KeyError(f"missing required operator column: {required}")
            frame = evaluation_table[keep_columns]
        else:
            frame = evaluation_table.copy()

        resolved = resolve_preview_policy(
            policy=policy,
            actions=list(requested_actions) if isinstance(requested_actions, tuple) else requested_actions,
            caption_columns=caption_columns,
            groupby=groupby,
            include_group_context=include_group_context,
            sort_by=sort_by,
            ascending=ascending,
        )
        if filters is not None:
            for column, value in filters.items():
                if column in frame.columns:
                    frame = frame[frame[column] == value]

        if action_column is not None and not resolved.include_all_actions:
            frame = frame[frame[action_column].isin(resolved.actions)]
        elif not resolved.include_all_actions:
            frame = frame[frame["final_action"].isin(resolved.actions)]

        options = PreviewHtmlOptions(
            action=None,
            filters=filters,
            groupby=resolved.groupby,
            include_group_context=resolved.include_group_context,
            sort_by=resolved.sort_by,
            ascending=resolved.ascending,
            caption_columns=resolved.caption_columns,
            max_rows=max_rows,
            max_groups=max_groups,
            max_items_per_group=max_items_per_group,
            thumbnail_size=thumbnail_size,
            columns_per_row=columns_per_row,
            operator_name=operator_name,
        )
        if resolved.sort_by:
            frame = frame.sort_values(by=resolved.sort_by, ascending=resolved.ascending, kind="mergesort")

        dataset_frame = self._load_parameter_table()[["image_id", "image_uri"]]
        dataset_path = self._run_dir() / "_result_preview_dataset.parquet"
        dataset = Dataset.write(dataset_frame, str(dataset_path))
        return write_preview_html(frame=frame.head(max_rows), path=path, dataset=dataset, options=options)

    def state(self) -> pd.DataFrame:
        """返回算子运行状态矩阵。"""
        state_path = self._run_paths().state_path
        if not state_path.exists():
            return pd.DataFrame(
                columns=["operator_name", "status", "processed_count", "skipped_count", "failed_count", "message"]
            )
        return build_state_frame(JsonRunStateStore().load(state_path))

    def result(self, operator_name: str) -> pd.DataFrame:
        """返回指定算子的 evaluation 列。"""
        operator_outputs = self._load_operator_outputs()
        if operator_name not in operator_outputs:
            raise KeyError(f"unknown operator_name: {operator_name}")
        table = self._load_evaluation_table()
        columns = [
            column
            for column in ["image_id", "image_uri", *operator_outputs[operator_name]]
            if column in table.columns
        ]
        return table[columns].copy()

    def explain(self, image_id: str) -> dict[str, object]:
        """返回单图解释信息。"""
        evaluation_table = self._load_evaluation_table()
        parameter_table = self._load_parameter_table()
        rows = evaluation_table[evaluation_table["image_id"] == image_id]
        if rows.empty:
            raise KeyError(f"image_id not found: {image_id}")

        parameter_rows = parameter_table[parameter_table["image_id"] == image_id]
        parameter_payload = parameter_rows.iloc[0].to_dict() if not parameter_rows.empty else {}
        evaluation_payload = rows.iloc[0].to_dict()
        explanation = {
            "image_id": image_id,
            "final_action": _normalize_value(evaluation_payload.get("final_action")),
            "final_reason": _normalize_value(evaluation_payload.get("final_reason")),
            "triggered_operator_names": _normalize_value(evaluation_payload.get("triggered_operator_names")),
            "evaluation": {_normalize_value(key): _normalize_value(value) for key, value in evaluation_payload.items()},
            "parameters": {_normalize_value(key): _normalize_value(value) for key, value in parameter_payload.items()},
            "operator_outputs": self._load_operator_outputs(),
            "parameter_manifest": self._load_parameter_manifest(),
            "relation_names": self._load_relation_names(),
        }
        return explanation

    def cleanup(self) -> None:
        """清理本次运行产物目录。"""
        shutil.rmtree(self._run_dir(), ignore_errors=True)
