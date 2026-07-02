from pathlib import Path

import pandas as pd
import pytest

from image_gallery.dataset import Dataset
from image_gallery.visualization import render_image_grid


def test_render_image_grid_from_dataset_uses_file_uri_and_caption(tmp_path: Path) -> None:
    image_path = tmp_path / "images" / "a.jpg"
    image_path.parent.mkdir()
    image_path.write_bytes(b"not-a-real-image")
    dataset_path = str(tmp_path / "raw.parquet")
    Dataset.write(
        pd.DataFrame(
            [
                {
                    "image_id": "img-1",
                    "image_uri": str(image_path),
                    "width": 10,
                    "height": 20,
                }
            ]
        ),
        dataset_path,
    )

    html = render_image_grid(Dataset.from_path(dataset_path), caption_columns=["image_id", "width"])

    assert image_path.as_uri() in html
    assert "img-1" in html
    assert "width: 10" in html


def test_render_image_grid_limits_rows_and_escapes_caption() -> None:
    frame = pd.DataFrame(
        [
            {"image_uri": "/tmp/a.jpg", "image_id": "<script>bad</script>"},
            {"image_uri": "/tmp/b.jpg", "image_id": "img-2"},
        ]
    )

    html = render_image_grid(frame, limit=1, caption_columns=["image_id"])

    assert "&lt;script&gt;bad&lt;/script&gt;" in html
    assert "img-2" not in html


def test_render_image_grid_uses_fixed_columns() -> None:
    frame = pd.DataFrame([{"image_uri": "/tmp/a.jpg", "image_id": "img-1"}])

    html = render_image_grid(frame, columns=3)

    assert "grid-template-columns:repeat(3, minmax(160px, 1fr))" in html


def test_render_image_grid_requires_image_uri_column() -> None:
    frame = pd.DataFrame([{"image_id": "img-1"}])

    with pytest.raises(ValueError, match="image_uri"):
        render_image_grid(frame)
