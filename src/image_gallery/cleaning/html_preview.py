from __future__ import annotations

import base64
from dataclasses import dataclass, field
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any, cast

import pandas as pd

from image_gallery.cleaning.preview import ACTION_PRIORITY
from image_gallery.dataset import Dataset


@dataclass(frozen=True)
class PreviewHtmlOptions:
    """HTML 预览参数。"""

    action: str | None = None
    operator_name: str | None = None
    filters: dict[str, object] | None = None
    groupby: str | None = None
    include_group_context: bool = False
    sort_by: list[str] | None = None
    ascending: bool | list[bool] = True
    caption_columns: list[str] | None = None
    max_rows: int = 200
    max_groups: int = 50
    max_items_per_group: int = 20
    thumbnail_size: int = 320
    columns_per_row: int = 6


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
        matched = cast(pd.DataFrame, matched[matched["final_action"] == action])
    for column, value in (filters or {}).items():
        matched = cast(pd.DataFrame, matched[matched[column] == value])

    if include_group_context:
        if groupby is None:
            raise ValueError("include_group_context requires groupby")
        group_values = cast(pd.Series, matched[groupby]).dropna().astype(str)
        group_values = cast(pd.Series, group_values[group_values != ""]).unique().tolist()
        matched = cast(pd.DataFrame, evaluation_table[evaluation_table[groupby].astype(str).isin(group_values)].copy())

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
        name = "" if cast(bool, pd.isna(group_name)) else str(group_name)
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


def write_preview_html(
    frame: pd.DataFrame,
    path: str | Path,
    *,
    dataset: Dataset,
    options: PreviewHtmlOptions,
) -> Path:
    """渲染并写出静态 HTML。"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    groups = build_preview_groups(
        frame,
        groupby=options.groupby,
        max_groups=options.max_groups,
        max_items_per_group=options.max_items_per_group,
    )
    html = _render_document(frame=frame, groups=groups, dataset=dataset, options=options)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _require_column(frame: pd.DataFrame, column: str, purpose: str) -> None:
    """校验预览所需字段存在。"""
    if column not in frame.columns:
        raise ValueError(f"missing preview {purpose} column: {column}")


def _render_document(
    *,
    frame: pd.DataFrame,
    groups: list[PreviewGroup],
    dataset: Dataset,
    options: PreviewHtmlOptions,
) -> str:
    """渲染完整 HTML 文档。"""
    if options.columns_per_row < 1:
        raise ValueError("columns_per_row must be at least 1")
    group_html = "\n".join(_render_group(group=group, dataset=dataset, options=options) for group in groups)
    summary_rows = [
        ("rows", len(frame)),
        ("operator_name", options.operator_name or ""),
        ("action", options.action or ""),
        ("groupby", options.groupby or ""),
        ("sort_by", ", ".join(options.sort_by or [])),
    ]
    summary_html = "".join(
        f"<div><strong>{escape(label)}</strong>: {escape(str(value))}</div>" for label, value in summary_rows
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Cleaning Preview</title>
  <style>
    body {{ margin: 24px; font-family: Arial, sans-serif; color: #1f2933; background: #f7f8fa; }}
    h1 {{ margin: 0 0 12px; font-size: 24px; }}
    h2 {{ margin: 0 0 12px; font-size: 18px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
      margin-bottom: 20px;
    }}
    .group {{ margin: 0 0 24px; padding: 16px; background: #ffffff; border: 1px solid #d8dee4; border-radius: 8px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat({options.columns_per_row}, minmax(0, 1fr));
      gap: 12px;
      align-items: start;
    }}
    figure {{ margin: 0; padding: 8px; border: 1px solid #e5e7eb; border-radius: 6px; background: #ffffff; }}
    img {{ width: 100%; height: auto; object-fit: contain; display: block; }}
    figcaption {{ margin-top: 6px; font-size: 12px; line-height: 1.4; overflow-wrap: anywhere; }}
    .error {{
      min-height: 80px;
      padding: 8px;
      color: #8a1f11;
      background: #fff1f0;
      border: 1px solid #ffccc7;
      border-radius: 6px;
      font-size: 12px;
      overflow-wrap: anywhere;
    }}
  </style>
</head>
<body>
  <h1>Cleaning Preview</h1>
  <section class="summary">{summary_html}</section>
  {group_html}
</body>
</html>
"""


def _render_group(*, group: PreviewGroup, dataset: Dataset, options: PreviewHtmlOptions) -> str:
    """渲染单个预览分组。"""
    cards = "\n".join(
        _render_card(row=row, dataset=dataset, options=options) for row in group.rows.to_dict(orient="records")
    )
    return (
        '<section class="group">'
        f"<h2>{escape(group.name)} <small>({group.total_count})</small></h2>"
        f'<div class="grid">{cards}</div>'
        "</section>"
    )


def _render_card(*, row: dict[str, Any], dataset: Dataset, options: PreviewHtmlOptions) -> str:
    """渲染单张图片卡片。"""
    image_uri = str(row.get("image_uri", ""))
    caption_html = "".join(_render_caption(row, column) for column in _caption_columns(row, options))
    try:
        data_uri = _thumbnail_data_uri(dataset=dataset, image_uri=image_uri, thumbnail_size=options.thumbnail_size)
        media_html = f'<img src="{escape(data_uri, quote=True)}" alt="{escape(image_uri, quote=True)}" />'
    except Exception as exc:
        media_html = f'<div class="error">Image read failed<br />{escape(image_uri)}<br />{escape(str(exc))}</div>'
    return f"<figure>{media_html}<figcaption>{caption_html}</figcaption></figure>"


def _caption_columns(row: dict[str, Any], options: PreviewHtmlOptions) -> list[str]:
    """返回当前卡片需要展示的 caption 字段。"""
    if options.caption_columns is not None:
        return options.caption_columns
    return ["image_id"] if "image_id" in row else []


def _render_caption(row: dict[str, Any], column: str) -> str:
    """渲染单个 caption 字段。"""
    if column not in row:
        return ""
    value = row[column]
    if pd.isna(value):
        return ""
    return f"<div>{escape(column)}: {escape(str(value))}</div>"


def _thumbnail_data_uri(*, dataset: Dataset, image_uri: str, thumbnail_size: int) -> str:
    """读取图片并编码为 HTML 可直接展示的 base64 缩略图。"""
    image = dataset.read_image(image_uri)
    image.thumbnail((thumbnail_size, thumbnail_size))
    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"
