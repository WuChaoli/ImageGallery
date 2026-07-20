"""CleanerResult 的 HTML 预览准备流程。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pandas as pd

from image_gallery.cleaning._result_artifacts import ResultArtifacts
from image_gallery.cleaning.html_preview import PreviewHtmlOptions, write_preview_html
from image_gallery.cleaning.preview_policy import PreviewPolicy, resolve_preview_policy
from image_gallery.dataset import Dataset


@dataclass(frozen=True)
class ResultPreviewRequest:
    """承载一次 CleanerResult HTML 预览请求。"""

    path: Path | str
    operator_name: str | None
    actions: str | list[str] | tuple[str, ...] | None
    filters: dict[str, object] | None
    groupby: str | None
    include_group_context: bool | None
    sort_by: list[str] | None
    ascending: bool | list[bool]
    caption_columns: list[str] | None
    max_rows: int | None
    max_groups: int | None
    max_items_per_group: int | None
    thumbnail_size: int | None
    columns_per_row: int | None


def write_result_preview(
    *,
    artifacts: ResultArtifacts,
    operator_preview_policies: dict[str, PreviewPolicy],
    dataset: Dataset | None,
    request: ResultPreviewRequest,
) -> Path:
    """解析预览策略、准备帧并写出 HTML。"""
    operator_outputs = artifacts.load_operator_outputs()
    evaluation_table = artifacts.load_evaluation_table()
    policy = _preview_policy(operator_preview_policies, request.operator_name)
    frame, action_column = _select_operator_frame(
        evaluation_table,
        operator_outputs,
        request.operator_name,
    )
    resolved = resolve_preview_policy(
        policy=policy,
        actions=list(request.actions) if isinstance(request.actions, tuple) else request.actions,
        caption_columns=request.caption_columns,
        groupby=request.groupby,
        include_group_context=request.include_group_context,
        sort_by=request.sort_by,
        ascending=request.ascending,
    )

    if request.filters is not None:
        for column, value in request.filters.items():
            if column in frame.columns:
                frame = cast(pd.DataFrame, frame[frame[column] == value])

    if not resolved.include_all_actions:
        selected_action_column = action_column or "final_action"
        frame = cast(
            pd.DataFrame,
            frame[cast(pd.Series, frame[selected_action_column]).isin(resolved.actions)],
        )

    options = PreviewHtmlOptions(
        action=None,
        filters=request.filters,
        groupby=resolved.groupby,
        include_group_context=resolved.include_group_context,
        sort_by=resolved.sort_by,
        ascending=resolved.ascending,
        caption_columns=resolved.caption_columns,
        max_rows=resolved.max_rows if request.max_rows is None else request.max_rows,
        max_groups=resolved.max_groups if request.max_groups is None else request.max_groups,
        max_items_per_group=(
            resolved.max_items_per_group if request.max_items_per_group is None else request.max_items_per_group
        ),
        thumbnail_size=(resolved.thumbnail_size if request.thumbnail_size is None else request.thumbnail_size),
        columns_per_row=(resolved.columns_per_row if request.columns_per_row is None else request.columns_per_row),
        operator_name=request.operator_name,
    )
    if resolved.sort_by:
        frame = frame.sort_values(  # pyright: ignore[reportCallIssue]
            by=resolved.sort_by,
            ascending=resolved.ascending,
            kind="mergesort",
        )

    preview_dataset = dataset if dataset is not None else _write_fallback_dataset(artifacts)
    return write_preview_html(
        frame=cast(pd.DataFrame, frame.head(options.max_rows)),
        path=request.path,
        dataset=preview_dataset,
        options=options,
    )


def _preview_policy(
    policies: dict[str, PreviewPolicy],
    operator_name: str | None,
) -> PreviewPolicy:
    """按算子名读取策略，缺省时返回默认策略。"""
    if operator_name is None:
        return PreviewPolicy()
    return policies.get(operator_name, PreviewPolicy())


def _select_operator_frame(
    evaluation_table: pd.DataFrame,
    operator_outputs: dict[str, list[str]],
    operator_name: str | None,
) -> tuple[pd.DataFrame, str | None]:
    """按算子选择预览列并返回其 action 列。"""
    if operator_name is None:
        return evaluation_table.copy(), None
    if operator_name not in operator_outputs:
        raise KeyError(f"unknown operator_name: {operator_name}")

    selected = operator_outputs[operator_name]
    action_columns = [column for column in selected if column.endswith("_action")]
    if not action_columns:
        raise ValueError(f"operator has no action column: {operator_name}")
    keep_columns = _deduplicate_columns(["image_id", "image_uri", "final_action", action_columns[0], *selected])
    for required in keep_columns:
        if required not in evaluation_table.columns:
            raise KeyError(f"missing required operator column: {required}")
    return cast(pd.DataFrame, evaluation_table[keep_columns]), action_columns[0]


def _deduplicate_columns(columns: list[str]) -> list[str]:
    """去重并保留列顺序。"""
    return list(dict.fromkeys(columns))


def _write_fallback_dataset(artifacts: ResultArtifacts) -> Dataset:
    """从 parameter table 写出仅供预览读取图片的 Dataset。"""
    dataset_frame = cast(
        pd.DataFrame,
        artifacts.load_parameter_table()[["image_id", "image_uri"]],
    )
    dataset_path = artifacts.run_dir() / "_result_preview_dataset.parquet"
    return Dataset.write(dataset_frame, str(dataset_path))
