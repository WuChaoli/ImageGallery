from html import escape
from pathlib import Path
from typing import Any, TypeAlias
from urllib.parse import urlparse

import pandas as pd

from image_gallery.dataset import Dataset

FrameSource: TypeAlias = Dataset | pd.DataFrame


def render_image_grid(
    source: FrameSource,
    *,
    limit: int = 24,
    image_column: str = "image_uri",
    caption_columns: list[str] | None = None,
    thumbnail_width: int = 160,
    columns: int | None = None,
) -> str:
    """生成适合 Notebook 展示的图片网格 HTML。"""
    # frame 是实际用于渲染的数据表；Dataset 输入会在这里读取成 DataFrame。
    frame = _source_to_frame(source).head(limit)
    if image_column not in frame.columns:
        raise ValueError(f"image column not found: {image_column}")

    # caption_columns 控制每张缩略图下面展示的字段，默认优先展示 image_id。
    captions = caption_columns
    if captions is None:
        captions = ["image_id"] if "image_id" in frame.columns else []

    cards = [
        _render_card(row=row, image_column=image_column, caption_columns=captions, thumbnail_width=thumbnail_width)
        for row in frame.to_dict("records")
    ]
    grid_columns = _grid_columns(thumbnail_width=thumbnail_width, columns=columns)
    return f'<div style="display:grid;grid-template-columns:{grid_columns};gap:12px;align-items:start;">' + "".join(
        cards
    ) + "</div>"


def show_image_grid(
    source: FrameSource,
    *,
    limit: int = 24,
    image_column: str = "image_uri",
    caption_columns: list[str] | None = None,
    thumbnail_width: int = 160,
    columns: int | None = None,
) -> object:
    """在 Notebook 中展示图片网格；非 Notebook 环境下返回 HTML 字符串。"""
    html = render_image_grid(
        source,
        limit=limit,
        image_column=image_column,
        caption_columns=caption_columns,
        thumbnail_width=thumbnail_width,
        columns=columns,
    )
    try:
        from IPython.display import HTML
    except ImportError:
        return html
    html_view: Any = HTML
    return html_view(html)


def _source_to_frame(source: FrameSource) -> pd.DataFrame:
    """把 Dataset 或 DataFrame 统一转换成 DataFrame。"""
    if isinstance(source, Dataset):
        return source.to_frame()
    return source


def _grid_columns(*, thumbnail_width: int, columns: int | None) -> str:
    """根据列数设置 CSS grid 模板。"""
    if columns is None:
        return f"repeat(auto-fill, minmax({thumbnail_width}px, 1fr))"
    if columns <= 0:
        raise ValueError("columns must be greater than 0")
    return f"repeat({columns}, minmax({thumbnail_width}px, 1fr))"


def _render_card(
    *,
    row: dict[str, Any],
    image_column: str,
    caption_columns: list[str],
    thumbnail_width: int,
) -> str:
    """渲染单张图片卡片。"""
    # image_src 是浏览器可使用的图片地址；本地绝对路径会转换为 file URI。
    image_src = _image_src(str(row[image_column]))
    caption_html = "".join(_render_caption(row, column) for column in caption_columns if column in row)
    return (
        '<figure style="margin:0;font:12px sans-serif;color:#333;">'
        f'<img src="{escape(image_src, quote=True)}" '
        f'style="width:{thumbnail_width}px;max-width:100%;height:auto;object-fit:contain;" />'
        f'<figcaption style="margin-top:4px;line-height:1.35;">{caption_html}</figcaption>'
        "</figure>"
    )


def _render_caption(row: dict[str, Any], column: str) -> str:
    """渲染单个说明字段。"""
    value = row[column]
    if pd.isna(value):
        return ""
    return f"<div>{escape(column)}: {escape(str(value))}</div>"


def _image_src(image_path: str) -> str:
    """把 image_uri/path 规范化为 HTML img 可用地址。"""
    parsed = urlparse(image_path)
    # 排除 Windows 盘符被误解析为 scheme 的情况（如 C:\... 的 scheme 为 'c'）
    if parsed.scheme and not (len(parsed.scheme) == 1 and parsed.scheme.isalpha()):
        return image_path

    path = Path(image_path).expanduser()
    if path.is_absolute():
        return path.as_uri()
    return image_path
