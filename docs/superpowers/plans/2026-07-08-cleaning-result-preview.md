# Cleaning Result Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a package-level `cleaner.preview_html(...)` API that writes static HTML previews for clean/drop/review/restricted cleaning results, with generic filtering, sorting, grouping, and optional group context.

**Architecture:** Keep preview query and rendering in a focused `image_gallery.cleaning.html_preview` module. `BasicCleaner.preview_html()` is a thin adapter that passes the current `evaluation_table` and `Dataset` into that module. The first version writes self-contained HTML with base64 thumbnails so `s3://` images are viewable without a notebook or temporary server.

**Tech Stack:** Python 3.10, pandas, Pillow, stdlib `base64`/`html`/`io`/`pathlib`, existing `Dataset.read_image`, pytest, ruff, mypy.

## Global Constraints

- Code paths, file names, Python symbols, and package APIs use English.
- User-facing docs and comments may use Simplified Chinese.
- Run and test with `.venv/bin/python`.
- Do not add runtime dependencies.
- Do not implement an HTTP preview server in this first version.
- Do not create per-operator preview renderers in this first version.
- Do not change cleaning execution, scheduling, export, or operator evaluation semantics.
- The preview source of truth is `evaluation_table`; relation-aware presets are deferred.
- `include_group_context=True` requires `groupby` and补回命中行所在分组的其他行。

---

## File Structure

- Create `src/image_gallery/cleaning/html_preview.py`
  - Owns preview filtering, grouping, thumbnail generation, and static HTML rendering.
  - Exposes `PreviewHtmlOptions`, `PreviewGroup`, `build_preview_frame`, `build_preview_groups`, and `write_preview_html`.
- Modify `src/image_gallery/cleaning/cleaner.py`
  - Adds abstract `preview_html(...) -> Path` to the base cleaner API.
- Modify `src/image_gallery/cleaning/basic.py`
  - Implements `BasicCleaner.preview_html(...)` as a thin adapter.
- Create `tests/unit/cleaning/test_html_preview.py`
  - Covers query filtering, sorting, grouping, context rows, validation, and HTML rendering.
- Modify `tests/integration/cleaning/test_basic_cleaner_export.py`
  - Adds an integration assertion that a real `BasicCleaner` run can write HTML.
- Modify `notebooks/operators_phash_duplicate_test.ipynb`
  - Adds one smoke cell that writes a grouped pHash drop preview HTML.

---

### Task 1: Preview Query And Grouping

**Files:**
- Create: `src/image_gallery/cleaning/html_preview.py`
- Test: `tests/unit/cleaning/test_html_preview.py`

**Interfaces:**
- Consumes:
  - `image_gallery.cleaning.preview.ACTION_PRIORITY`
  - `pd.DataFrame` with at least `image_id`, `image_uri`, and usually `final_action`
- Produces:
  - `PreviewHtmlOptions`
  - `PreviewGroup`
  - `build_preview_frame(evaluation_table: pd.DataFrame, *, action: str | None = None, filters: dict[str, object] | None = None, groupby: str | None = None, include_group_context: bool = False, sort_by: list[str] | None = None, ascending: bool | list[bool] = True, max_rows: int = 200) -> pd.DataFrame`
  - `build_preview_groups(frame: pd.DataFrame, *, groupby: str | None = None, max_groups: int = 50, max_items_per_group: int = 20) -> list[PreviewGroup]`

- [ ] **Step 1: Write failing tests for frame filtering, group context, sorting, and validation**

Add this initial content to `tests/unit/cleaning/test_html_preview.py`:

```python
import pandas as pd
import pytest

from image_gallery.cleaning.html_preview import build_preview_frame, build_preview_groups


def _preview_input_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "image_id": ["keeper-a", "drop-a", "keeper-b", "drop-b", "clean"],
            "image_uri": ["a.png", "b.png", "c.png", "d.png", "e.png"],
            "final_action": ["keep", "drop", "keep", "drop", "keep"],
            "duplicate_group_id": ["group-a", "group-a", "group-b", "group-b", ""],
            "duplicate_count": [2, 2, 2, 2, 1],
            "distance": [0, 3, 0, 1, pd.NA],
            "reason": ["", "distance=3", "", "distance=1", ""],
        }
    )


def test_build_preview_frame_filters_action_and_exact_filters() -> None:
    frame = build_preview_frame(
        _preview_input_frame(),
        action="drop",
        filters={"duplicate_group_id": "group-a"},
    )

    assert frame["image_id"].tolist() == ["drop-a"]


def test_build_preview_frame_includes_group_context_rows_before_sorting() -> None:
    frame = build_preview_frame(
        _preview_input_frame(),
        action="drop",
        groupby="duplicate_group_id",
        include_group_context=True,
        sort_by=["duplicate_group_id", "distance"],
        ascending=[True, True],
    )

    assert frame["image_id"].tolist() == ["keeper-a", "drop-a", "keeper-b", "drop-b"]


def test_build_preview_frame_sorts_and_limits_rows() -> None:
    frame = build_preview_frame(
        _preview_input_frame(),
        sort_by=["distance"],
        ascending=False,
        max_rows=2,
    )

    assert frame["image_id"].tolist() == ["drop-a", "drop-b"]


def test_build_preview_frame_rejects_invalid_fields_and_actions() -> None:
    source = _preview_input_frame()

    with pytest.raises(ValueError, match="unsupported preview action"):
        build_preview_frame(source, action="archive")
    with pytest.raises(ValueError, match="missing preview filter column"):
        build_preview_frame(source, filters={"missing": "x"})
    with pytest.raises(ValueError, match="missing preview sort column"):
        build_preview_frame(source, sort_by=["missing"])
    with pytest.raises(ValueError, match="missing preview groupby column"):
        build_preview_frame(source, groupby="missing", include_group_context=True)
    with pytest.raises(ValueError, match="include_group_context requires groupby"):
        build_preview_frame(source, include_group_context=True)


def test_build_preview_groups_without_groupby_returns_single_group() -> None:
    frame = _preview_input_frame().head(3)

    groups = build_preview_groups(frame, max_items_per_group=2)

    assert len(groups) == 1
    assert groups[0].name == "All rows"
    assert groups[0].total_count == 3
    assert groups[0].rows["image_id"].tolist() == ["keeper-a", "drop-a"]


def test_build_preview_groups_preserves_group_order_and_limits_items() -> None:
    frame = _preview_input_frame()

    groups = build_preview_groups(
        frame,
        groupby="duplicate_group_id",
        max_groups=2,
        max_items_per_group=1,
    )

    assert [group.name for group in groups] == ["group-a", "group-b"]
    assert [group.total_count for group in groups] == [2, 2]
    assert [group.rows["image_id"].tolist() for group in groups] == [["keeper-a"], ["keeper-b"]]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_html_preview.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'image_gallery.cleaning.html_preview'`.

- [ ] **Step 3: Implement the query and grouping functions**

Create `src/image_gallery/cleaning/html_preview.py` with this initial content:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

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
    for column in (filters or {}):
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
```

- [ ] **Step 4: Run tests to verify Task 1 passes**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_html_preview.py -q
```

Expected: PASS for the six Task 1 tests.

- [ ] **Step 5: Run lint for changed files**

Run:

```bash
.venv/bin/python -m ruff check src/image_gallery/cleaning/html_preview.py tests/unit/cleaning/test_html_preview.py
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add src/image_gallery/cleaning/html_preview.py tests/unit/cleaning/test_html_preview.py
git commit -m "feat: add cleaning preview query helpers"
```

---

### Task 2: Static HTML Renderer With Base64 Thumbnails

**Files:**
- Modify: `src/image_gallery/cleaning/html_preview.py`
- Modify: `tests/unit/cleaning/test_html_preview.py`

**Interfaces:**
- Consumes:
  - `PreviewHtmlOptions`
  - `build_preview_groups(...)`
  - `Dataset.read_image(image_uri: str) -> PIL.Image.Image`
- Produces:
  - `write_preview_html(frame: pd.DataFrame, path: str | Path, *, dataset: Dataset, options: PreviewHtmlOptions) -> Path`

- [ ] **Step 1: Add failing HTML renderer tests**

Append these tests to `tests/unit/cleaning/test_html_preview.py`:

```python
from pathlib import Path

from PIL import Image

from image_gallery.cleaning.html_preview import PreviewHtmlOptions, write_preview_html
from image_gallery.dataset import Dataset


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (24, 16), color=color).save(path)


def test_write_preview_html_renders_groups_and_base64_images(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    _write_image(first, (255, 0, 0))
    _write_image(second, (0, 255, 0))
    frame = pd.DataFrame(
        {
            "image_id": ["keeper-a", "drop-a"],
            "image_uri": [str(first), str(second)],
            "final_action": ["keep", "drop"],
            "duplicate_group_id": ["group-a", "group-a"],
            "distance": [0, 2],
        }
    )
    dataset = Dataset.write(frame[["image_id", "image_uri"]], str(tmp_path / "raw.parquet"))

    output_path = write_preview_html(
        frame,
        tmp_path / "preview.html",
        dataset=dataset,
        options=PreviewHtmlOptions(
            action="drop",
            groupby="duplicate_group_id",
            include_group_context=True,
            caption_columns=["image_id", "final_action", "distance"],
            thumbnail_size=96,
        ),
    )

    html = output_path.read_text(encoding="utf-8")
    assert output_path == tmp_path / "preview.html"
    assert "Cleaning Preview" in html
    assert "group-a" in html
    assert "keeper-a" in html
    assert "drop-a" in html
    assert "data:image/jpeg;base64," in html


def test_write_preview_html_records_image_read_errors(tmp_path: Path) -> None:
    missing = tmp_path / "missing.png"
    frame = pd.DataFrame(
        {
            "image_id": ["missing"],
            "image_uri": [str(missing)],
            "final_action": ["drop"],
        }
    )
    dataset = Dataset.write(frame[["image_id", "image_uri"]], str(tmp_path / "raw.parquet"))

    output_path = write_preview_html(
        frame,
        tmp_path / "preview.html",
        dataset=dataset,
        options=PreviewHtmlOptions(caption_columns=["image_id"]),
    )

    html = output_path.read_text(encoding="utf-8")
    assert "Image read failed" in html
    assert "missing.png" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_html_preview.py -q
```

Expected: FAIL with `ImportError` because `write_preview_html` is not exported yet.

- [ ] **Step 3: Implement renderer helpers**

Add `write_preview_html` to `src/image_gallery/cleaning/html_preview.py` with the renderer helpers below. The final module should include these additional imports:

```python
import base64
from html import escape
from io import BytesIO
from typing import Any
```

Add this implementation below `build_preview_groups`:

```python
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


def _render_document(
    *,
    frame: pd.DataFrame,
    groups: list[PreviewGroup],
    dataset: Dataset,
    options: PreviewHtmlOptions,
) -> str:
    """渲染完整 HTML 文档。"""
    group_html = "\n".join(_render_group(group=group, dataset=dataset, options=options) for group in groups)
    summary_rows = [
        ("rows", len(frame)),
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
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; margin-bottom: 20px; }}
    .group {{ margin: 0 0 24px; padding: 16px; background: #ffffff; border: 1px solid #d8dee4; border-radius: 8px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax({options.thumbnail_size}px, 1fr)); gap: 12px; align-items: start; }}
    figure {{ margin: 0; padding: 8px; border: 1px solid #e5e7eb; border-radius: 6px; background: #ffffff; }}
    img {{ width: {options.thumbnail_size}px; max-width: 100%; height: auto; object-fit: contain; display: block; }}
    figcaption {{ margin-top: 6px; font-size: 12px; line-height: 1.4; overflow-wrap: anywhere; }}
    .error {{ min-height: 80px; padding: 8px; color: #8a1f11; background: #fff1f0; border: 1px solid #ffccc7; border-radius: 6px; font-size: 12px; overflow-wrap: anywhere; }}
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
```

Keep the Task 1 query helpers unchanged; Task 2 only adds renderer imports and functions.

- [ ] **Step 4: Run renderer unit tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_html_preview.py -q
```

Expected: PASS.

- [ ] **Step 5: Run lint and mypy on the new module**

Run:

```bash
.venv/bin/python -m ruff check src/image_gallery/cleaning/html_preview.py tests/unit/cleaning/test_html_preview.py
.venv/bin/python -m mypy src/image_gallery/cleaning/html_preview.py
```

Expected: both PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/image_gallery/cleaning/html_preview.py tests/unit/cleaning/test_html_preview.py
git commit -m "feat: render cleaning preview html"
```

---

### Task 3: Cleaner API Integration

**Files:**
- Modify: `src/image_gallery/cleaning/cleaner.py`
- Modify: `src/image_gallery/cleaning/basic.py`
- Modify: `tests/integration/cleaning/test_basic_cleaner_export.py`

**Interfaces:**
- Consumes:
  - `PreviewHtmlOptions`
  - `build_preview_frame(...)`
  - `write_preview_html(...)`
  - `BasicCleaner._require_run()`
- Produces:
  - `Cleaner.preview_html(...) -> Path`
  - `BasicCleaner.preview_html(...) -> Path`

- [ ] **Step 1: Add failing integration test for `BasicCleaner.preview_html`**

Append this test to `tests/integration/cleaning/test_basic_cleaner_export.py`:

```python
def test_basic_cleaner_writes_html_preview(tmp_path: Path) -> None:
    ok = tmp_path / "ok.png"
    broken = tmp_path / "broken.jpg"
    _write_image(ok, (16, 16), (10, 20, 30))
    broken.write_bytes(b"not an image")
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["ok", "bad"],
                "image_uri": [str(ok), str(broken)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )
    cleaner = BasicCleaner([{"format.decode_check": {"action": "drop"}}])
    cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    output_path = cleaner.preview_html(
        tmp_path / "preview.html",
        action="drop",
        caption_columns=["image_id", "final_action", "decode_check_reason"],
    )

    html = output_path.read_text(encoding="utf-8")
    assert output_path == tmp_path / "preview.html"
    assert "Cleaning Preview" in html
    assert "bad" in html
    assert "final_action: drop" in html
```

- [ ] **Step 2: Run the integration test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/integration/cleaning/test_basic_cleaner_export.py::test_basic_cleaner_writes_html_preview -q
```

Expected: FAIL with `AttributeError: 'BasicCleaner' object has no attribute 'preview_html'`.

- [ ] **Step 3: Add abstract method to `Cleaner`**

In `src/image_gallery/cleaning/cleaner.py`, add this method after `preview(...)`:

```python
    @abstractmethod
    def preview_html(
        self,
        path: str | Path,
        *,
        action: str | None = None,
        filters: dict[str, object] | None = None,
        groupby: str | None = None,
        include_group_context: bool = False,
        sort_by: list[str] | None = None,
        ascending: bool | list[bool] = True,
        caption_columns: list[str] | None = None,
        max_rows: int = 200,
        max_groups: int = 50,
        max_items_per_group: int = 20,
        thumbnail_size: int = 160,
    ) -> Path:
        """把当前清洗结果写出为静态 HTML 预览页。"""
```

- [ ] **Step 4: Implement `BasicCleaner.preview_html`**

In `src/image_gallery/cleaning/basic.py`, add this import:

```python
from image_gallery.cleaning.html_preview import PreviewHtmlOptions, build_preview_frame, write_preview_html
```

Add this method after `preview(...)`:

```python
    def preview_html(
        self,
        path: str | Path,
        *,
        action: str | None = None,
        filters: dict[str, object] | None = None,
        groupby: str | None = None,
        include_group_context: bool = False,
        sort_by: list[str] | None = None,
        ascending: bool | list[bool] = True,
        caption_columns: list[str] | None = None,
        max_rows: int = 200,
        max_groups: int = 50,
        max_items_per_group: int = 20,
        thumbnail_size: int = 160,
    ) -> Path:
        """把当前清洗结果写出为静态 HTML 预览页。"""
        context, tables, _ = self._require_run()
        options = PreviewHtmlOptions(
            action=action,
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
        )
        frame = build_preview_frame(
            tables.evaluation_table,
            action=action,
            filters=filters,
            groupby=groupby,
            include_group_context=include_group_context,
            sort_by=sort_by,
            ascending=ascending,
            max_rows=max_rows,
        )
        return write_preview_html(frame, path, dataset=context.dataset, options=options)
```

- [ ] **Step 5: Run the new integration test**

Run:

```bash
.venv/bin/python -m pytest tests/integration/cleaning/test_basic_cleaner_export.py::test_basic_cleaner_writes_html_preview -q
```

Expected: PASS.

- [ ] **Step 6: Run focused cleaning tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_html_preview.py tests/integration/cleaning/test_basic_cleaner_export.py -q
```

Expected: PASS.

- [ ] **Step 7: Run ruff and mypy for touched package files**

Run:

```bash
.venv/bin/python -m ruff check src/image_gallery/cleaning/cleaner.py src/image_gallery/cleaning/basic.py src/image_gallery/cleaning/html_preview.py tests/unit/cleaning/test_html_preview.py tests/integration/cleaning/test_basic_cleaner_export.py
.venv/bin/python -m mypy src/image_gallery
```

Expected: both PASS.

- [ ] **Step 8: Commit Task 3**

```bash
git add src/image_gallery/cleaning/cleaner.py src/image_gallery/cleaning/basic.py tests/integration/cleaning/test_basic_cleaner_export.py
git commit -m "feat: add cleaner html preview api"
```

---

### Task 4: pHash Notebook Smoke Preview

**Files:**
- Modify: `notebooks/operators_phash_duplicate_test.ipynb`
- Optionally Modify: `examples/README.md` only if the notebook index needs a new note about HTML preview.

**Interfaces:**
- Consumes:
  - `BasicCleaner.preview_html(...) -> Path`
  - Existing pHash notebook variables: `cleaner`, `library_root`, `export_dir`
- Produces:
  - `datasets/tests/operators_phash_duplicate/preview.html`

- [ ] **Step 1: Add notebook cell that writes pHash grouped drop preview**

Use a small notebook-editing script or Jupyter UI to add this code cell after the clean/drop export cell in `notebooks/operators_phash_duplicate_test.ipynb`:

```python
# 生成静态 HTML 预览页，重点检查 pHash drop 结果的分组效果。
preview_path = cleaner.preview_html(
    library_root / "preview.html",
    action="drop",
    groupby="perceptual_duplicate_group_id",
    include_group_context=True,
    sort_by=["perceptual_duplicate_count", "perceptual_duplicate_distance"],
    ascending=[False, True],
    caption_columns=[
        "image_id",
        "final_action",
        "perceptual_duplicate_distance",
        "perceptual_duplicate_reason",
    ],
    max_groups=20,
    max_items_per_group=12,
    thumbnail_size=160,
)

print(f"preview_html_path={preview_path}")
assert preview_path.exists()
```

- [ ] **Step 2: Update final notebook assertions**

In the final assertion cell of `notebooks/operators_phash_duplicate_test.ipynb`, add:

```python
assert (library_root / "preview.html").exists()
```

- [ ] **Step 3: Execute the notebook with the existing lightweight executor**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

notebook_path = Path("notebooks/operators_phash_duplicate_test.ipynb")
notebook = json.loads(notebook_path.read_text())
namespace = {"__name__": "__notebook__"}
for index, cell in enumerate(notebook["cells"], start=1):
    if cell.get("cell_type") != "code":
        continue
    source = "".join(cell.get("source", []))
    print(f"--- cell {index} ---")
    exec(compile(source, f"{notebook_path}:cell{index}", "exec"), namespace)
PY
```

Expected:

```text
preview_html_path=/home/wuchaoli/codespace/ImageGallery/datasets/tests/operators_phash_duplicate/preview.html
PASS: phash duplicate operator notebook smoke completed
```

- [ ] **Step 4: Verify the HTML file exists and contains group data**

Run:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path

path = Path("datasets/tests/operators_phash_duplicate/preview.html")
html = path.read_text(encoding="utf-8")
print(path)
print("bytes", path.stat().st_size)
assert "Cleaning Preview" in html
assert "perceptual" in html
assert "data:image/jpeg;base64," in html
PY
```

Expected: command exits 0 and prints a nonzero byte count.

- [ ] **Step 5: Run final verification**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_html_preview.py tests/integration/cleaning/test_basic_cleaner_export.py -q
.venv/bin/python -m ruff check src/image_gallery/cleaning tests/unit/cleaning/test_html_preview.py tests/integration/cleaning/test_basic_cleaner_export.py
.venv/bin/python -m mypy src/image_gallery
```

Expected: all PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add notebooks/operators_phash_duplicate_test.ipynb
git commit -m "test: preview phash duplicate results as html"
```

---

## Self-Review

### Spec Coverage

- Package-level official preview API: Task 3 adds `Cleaner.preview_html` and `BasicCleaner.preview_html`.
- Static HTML output: Task 2 implements `write_preview_html`.
- Filtering, grouping, sorting, limits: Task 1 implements and tests `build_preview_frame` and `build_preview_groups`.
- Clean/drop/review/restricted action views: Task 1 validates action against existing `ACTION_PRIORITY`.
- MinIO-backed image support: Task 2 uses `Dataset.read_image`, so `s3://` works when the dataset has storage.
- No temporary server: no task implements server code.
- No per-operator renderer: pHash notebook calls generic `groupby` preview only.
- `include_group_context=True`: Task 1 implements context row expansion; Task 4 uses it for pHash drop groups.

### Completeness Scan

The plan contains no incomplete production steps. Task 1 implements only query helpers; Task 2 introduces the renderer API with its final behavior.

### Type Consistency

- `path` is `str | Path` in both abstract and concrete `preview_html`.
- `ascending` is `bool | list[bool]` consistently across options, query helper, and API method.
- `PreviewHtmlOptions` fields match the `Cleaner.preview_html` keyword parameters.
- `write_preview_html` receives a filtered `frame`, the current `Dataset`, and immutable `PreviewHtmlOptions`.
