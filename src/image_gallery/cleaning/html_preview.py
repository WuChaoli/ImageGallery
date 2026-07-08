from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from image_gallery.cleaning.preview import ACTION_PRIORITY


@dataclass(frozen=True)
class PreviewHtmlOptions:
    """HTML 预览参数。"""

    action: str | None = None
    filters: dict[str, object] | None = None
    groupby: str | None = None
    include_group_context: bool = False
    sort_by: list[str] | None = None
    ascending: bool | list[bool] = True
    caption_columns: list[str] | None = None
    max_rows: int = 200
    max_groups: int = 50
    max_items_per_group: int = 20
    thumbnail_size: int = 160


@dataclass(frozen=True)
class PreviewGroup:
    """一个预览分组。"""

    name: str
    total_count: int
    rows: pd.DataFrame = field(compare=False)


def build_preview_frame(
    evaluation_table: pd.DataFrame,
    *,
    action: str | None = None,
    filters: dict[str, object] | None = None,
    groupby: str | None = None,
    include_group_context: bool = False,
    sort_by: list[str] | None = None,
    ascending: bool | list[bool] = True,
    max_rows: int = 200,
) -> pd.DataFrame:
    """按过滤、上下文和排序参数构造待预览行。"""
    if include_group_context and not groupby:
        raise ValueError("include_group_context requires groupby")
    if action is not None and action not in ACTION_PRIORITY:
        raise ValueError(f"unsupported preview action: {action}")
    if groupby is not None:
        _require_column(evaluation_table, groupby, "groupby")
    for column in filters or {}:
        _require_column(evaluation_table, column, "filter")
    for column in sort_by or []:
        _require_column(evaluation_table, column, "sort")

    matched = evaluation_table.copy()
    if action is not None:
        _require_column(matched, "final_action", "action")
        matched = matched[matched["final_action"] == action]
    for column, value in (filters or {}).items():
        matched = matched[matched[column] == value]

    if include_group_context:
        if groupby is None:
            raise ValueError("include_group_context requires groupby")
        group_values = matched[groupby].dropna().astype(str)
        group_values = group_values[group_values != ""].unique().tolist()
        matched = evaluation_table[evaluation_table[groupby].astype(str).isin(group_values)].copy()

    if sort_by:
        matched = matched.sort_values(by=sort_by, ascending=ascending, kind="mergesort")
    return matched.head(max_rows).reset_index(drop=True)


def build_preview_groups(
    frame: pd.DataFrame,
    *,
    groupby: str | None = None,
    max_groups: int = 50,
    max_items_per_group: int = 20,
) -> list[PreviewGroup]:
    """把待预览行转为分组结构。"""
    if groupby is None:
        return [
            PreviewGroup(
                name="All rows",
                total_count=len(frame),
                rows=frame.head(max_items_per_group).reset_index(drop=True),
            )
        ]

    _require_column(frame, groupby, "groupby")
    groups: list[PreviewGroup] = []
    for group_name, group_frame in frame.groupby(groupby, sort=False, dropna=False):
        name = "" if pd.isna(group_name) else str(group_name)
        if not name:
            continue
        groups.append(
            PreviewGroup(
                name=name,
                total_count=len(group_frame),
                rows=group_frame.head(max_items_per_group).reset_index(drop=True),
            )
        )
        if len(groups) >= max_groups:
            break
    return groups


def _require_column(frame: pd.DataFrame, column: str, purpose: str) -> None:
    """校验预览所需字段存在。"""
    if column not in frame.columns:
        raise ValueError(f"missing preview {purpose} column: {column}")
