from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from image_gallery.cleaning.html_preview import (
    PreviewHtmlOptions,
    build_preview_frame,
    build_preview_groups,
    write_preview_html,
)
from image_gallery.dataset import Dataset


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
