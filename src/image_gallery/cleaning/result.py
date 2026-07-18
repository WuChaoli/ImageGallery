"""Cleaner 运行结果对象及导出、预览、解释能力。"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd

from image_gallery.cleaning._result_artifacts import ResultArtifacts, read_status
from image_gallery.cleaning._result_exports import (
    export_debug_bundle,
    export_manifest,
    export_relation,
    export_table,
)
from image_gallery.cleaning._result_preview import ResultPreviewRequest, write_result_preview
from image_gallery.cleaning.export import export_cleaning_result
from image_gallery.cleaning.preview import PreviewResult, build_preview
from image_gallery.cleaning.preview_policy import PreviewPolicy
from image_gallery.cleaning.state import JsonRunStateStore, build_state_frame
from image_gallery.cleaning.tables import CleaningTables
from image_gallery.dataset import Dataset


def read_result_status(cache_root: Path, run_id: str) -> str:
    """读取 `run_state.sqlite` 中的运行状态。"""
    return read_status(cache_root, run_id)


def _normalize_value(value: object) -> object:
    """将 Pandas 的缺失值转为空字符串，便于 HTML/JSON 输出。"""
    if cast(bool, pd.isna(cast(Any, value))):
        return ""
    return value


@dataclass(frozen=True)
class CleanerResult:
    """清洗一次运行后的只读结果入口。"""

    run_id: str
    _cache_root: Path
    _operator_preview_policies: dict[str, PreviewPolicy]
    _dataset: Dataset | None

    def __init__(
        self,
        run_id: str,
        cache_root: Path,
        *,
        operator_preview_policies: dict[str, PreviewPolicy] | None = None,
        dataset: Dataset | None = None,
    ) -> None:
        """构造函数。"""
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "_cache_root", Path(cache_root))
        object.__setattr__(
            self,
            "_operator_preview_policies",
            dict(operator_preview_policies or {}),
        )
        object.__setattr__(self, "_dataset", dataset)

    def _artifacts(self) -> ResultArtifacts:
        """返回本次运行的产物访问对象。"""
        return ResultArtifacts(cache_root=self._cache_root, run_id=self.run_id)

    def _run_dir(self) -> Path:
        """返回本次运行目录。"""
        return self._artifacts().run_dir()

    def status(self) -> str:
        """返回运行状态。"""
        return read_result_status(self._cache_root, self.run_id)

    def export_table(self, kind: str, path: Path | str) -> Path:
        """把某张运行表拷贝到目标路径。"""
        return export_table(self._artifacts(), kind, path)

    def export_manifest(self, kind: str, path: Path | str) -> Path:
        """导出指定的运行时 manifest 到给定路径。"""
        return export_manifest(self._artifacts(), kind, path)

    def export_relations(self, relation_name: str, path: Path | str) -> Path:
        """把指定 relation 表复制到用户路径，不暴露内部运行目录。"""
        return export_relation(self._artifacts(), relation_name, path)

    def export_debug_bundle(self, path: Path | str) -> Path:
        """导出只读调试包，包含表、manifest、状态和 relation 副本。"""
        return export_debug_bundle(self._artifacts(), path)

    def export(self, kind: str, path: Path | str) -> Dataset:
        """按 kind 导出清洗产物并返回 Dataset。"""
        artifacts = self._artifacts()
        tables = CleaningTables(
            parameter_table=artifacts.load_parameter_table(),
            evaluation_table=artifacts.load_evaluation_table(),
            operator_outputs=artifacts.load_operator_outputs(),
            parameter_manifest=artifacts.load_parameter_manifest(),
        )
        export_cleaning_result(
            kind=str(kind).strip().lower(),
            tables=tables,
            output_path=str(path),
        )
        return Dataset.load(str(path))

    def preview(self, limit: int = 20) -> PreviewResult:
        """返回 preview 概览。"""
        artifacts = self._artifacts()
        return build_preview(
            evaluation_table=artifacts.load_evaluation_table(),
            operator_outputs=artifacts.load_operator_outputs(),
            limit=limit,
        )

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
        max_rows: int | None = None,
        max_groups: int | None = None,
        max_items_per_group: int | None = None,
        thumbnail_size: int | None = None,
        columns_per_row: int | None = None,
        action: str | None = None,
    ) -> Path:
        """把预览结果渲染到 HTML。"""
        requested_actions = actions
        if requested_actions is None and action is not None:
            requested_actions = action

        return write_result_preview(
            artifacts=self._artifacts(),
            operator_preview_policies=self._operator_preview_policies,
            dataset=self._dataset,
            request=ResultPreviewRequest(
                path=path,
                operator_name=operator_name,
                actions=requested_actions,
                filters=filters,
                groupby=groupby,
                include_group_context=include_group_context,
                sort_by=sort_by,
                ascending=ascending,
                caption_columns=caption_columns,
                max_rows=max_rows,
                max_groups=max_groups,
                max_items_per_group=max_items_per_group,
                thumbnail_size=thumbnail_size,
                columns_per_row=columns_per_row,
            ),
        )

    def state(self) -> pd.DataFrame:
        """返回算子运行状态矩阵。"""
        state_path = self._artifacts().run_paths().state_path
        if not state_path.exists():
            return pd.DataFrame(
                columns=["operator_name", "status", "processed_count", "skipped_count", "failed_count", "message"]
            )
        return build_state_frame(JsonRunStateStore().load(state_path))

    def result(self, operator_name: str) -> pd.DataFrame:
        """返回指定算子的 evaluation 列。"""
        artifacts = self._artifacts()
        operator_outputs = artifacts.load_operator_outputs()
        if operator_name not in operator_outputs:
            raise KeyError(f"unknown operator_name: {operator_name}")
        table = artifacts.load_evaluation_table()
        columns = [
            column for column in ["image_id", "image_uri", *operator_outputs[operator_name]] if column in table.columns
        ]
        return cast(pd.DataFrame, table[columns]).copy()

    def explain(self, image_id: str) -> dict[str, object]:
        """返回单图解释信息。"""
        artifacts = self._artifacts()
        evaluation_table = artifacts.load_evaluation_table()
        parameter_table = artifacts.load_parameter_table()
        rows = evaluation_table[evaluation_table["image_id"] == image_id]
        if rows.empty:
            raise KeyError(f"image_id not found: {image_id}")

        parameter_rows = parameter_table[parameter_table["image_id"] == image_id]
        parameter_payload = parameter_rows.iloc[0].to_dict() if not parameter_rows.empty else {}
        evaluation_payload = rows.iloc[0].to_dict()
        return {
            "image_id": image_id,
            "final_action": _normalize_value(evaluation_payload.get("final_action")),
            "final_reason": _normalize_value(evaluation_payload.get("final_reason")),
            "triggered_operator_names": _normalize_value(evaluation_payload.get("triggered_operator_names")),
            "evaluation": {_normalize_value(key): _normalize_value(value) for key, value in evaluation_payload.items()},
            "parameters": {_normalize_value(key): _normalize_value(value) for key, value in parameter_payload.items()},
            "operator_outputs": artifacts.load_operator_outputs(),
            "parameter_manifest": artifacts.load_parameter_manifest(),
            "relation_names": artifacts.load_relation_names(),
        }

    def cleanup(self) -> None:
        """清理本次运行产物目录。"""
        shutil.rmtree(self._artifacts().run_dir(), ignore_errors=True)
