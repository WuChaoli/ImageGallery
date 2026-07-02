from pathlib import Path

import pandas as pd
import pytest

from image_gallery.dataset import Dataset


def _html_text(value: object) -> str:
    return str(getattr(value, "data", value))


def _write_draw_dataset(tmp_path: Path) -> Dataset:
    dataset_path = str(tmp_path / "raw.parquet")
    Dataset.write(
        pd.DataFrame(
            [
                {"image_id": "img-1", "image_uri": str(tmp_path / "a.jpg"), "import_status": "imported", "width": 10},
                {"image_id": "img-2", "image_uri": str(tmp_path / "b.jpg"), "import_status": "failed", "width": 30},
                {"image_id": "img-3", "image_uri": str(tmp_path / "c.jpg"), "import_status": "imported", "width": 20},
                {"image_id": "img-4", "image_uri": str(tmp_path / "d.jpg"), "import_status": "imported", "width": 40},
                {"image_id": "img-5", "image_uri": str(tmp_path / "e.jpg"), "import_status": "imported", "width": 50},
                {"image_id": "img-6", "image_uri": str(tmp_path / "f.jpg"), "import_status": "imported", "width": 60},
                {"image_id": "img-7", "image_uri": str(tmp_path / "g.jpg"), "import_status": "imported", "width": 70},
            ]
        ),
        dataset_path,
    )
    return Dataset.from_path(dataset_path)


def test_dataset_draw_filters_rows(tmp_path: Path) -> None:
    dataset = _write_draw_dataset(tmp_path)

    html = _html_text(dataset.draw(filter={"import_status": "failed"}, caption_columns=["image_id"]))

    assert "img-2" in html
    assert "img-1" not in html


def test_dataset_draw_sorts_rows(tmp_path: Path) -> None:
    dataset = _write_draw_dataset(tmp_path)

    html = _html_text(dataset.draw(sort={"width": "desc"}, max_num=2, caption_columns=["image_id", "width"]))

    assert html.index("img-7") < html.index("img-6")
    assert "img-5" not in html


def test_dataset_draw_size_limits_grid_before_max_num(tmp_path: Path) -> None:
    dataset = _write_draw_dataset(tmp_path)

    html = _html_text(dataset.draw(size=(2, 3), max_num=10, caption_columns=["image_id"]))

    assert html.count("<figure") == 6
    assert "grid-template-columns:repeat(3," in html


def test_dataset_draw_max_num_limits_grid_before_size(tmp_path: Path) -> None:
    dataset = _write_draw_dataset(tmp_path)

    html = _html_text(dataset.draw(size=(3, 3), max_num=4, caption_columns=["image_id"]))

    assert html.count("<figure") == 4


def test_dataset_draw_requires_image_uri_column(tmp_path: Path) -> None:
    dataset_path = str(tmp_path / "raw.parquet")
    Dataset.write(pd.DataFrame([{"image_id": "img-1"}]), dataset_path)

    with pytest.raises(ValueError, match="image_uri"):
        Dataset.from_path(dataset_path).draw()


def test_dataset_draw_rejects_invalid_sort_direction(tmp_path: Path) -> None:
    dataset = _write_draw_dataset(tmp_path)

    with pytest.raises(ValueError, match="sort direction"):
        dataset.draw(sort={"width": "down"})
