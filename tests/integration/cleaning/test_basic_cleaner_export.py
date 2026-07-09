from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


def _write_image(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
    Image.new("RGB", size, color=color).save(path)


def test_basic_cleaner_exports_builtin_views_and_preserves_counts(tmp_path: Path) -> None:
    ok = tmp_path / "ok.png"
    small = tmp_path / "small.png"
    broken = tmp_path / "broken.jpg"
    _write_image(ok, (16, 16), (10, 20, 30))
    _write_image(small, (4, 4), (200, 210, 220))
    broken.write_bytes(b"not an image")
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["ok", "small", "bad"],
                "image_uri": [str(ok), str(small), str(broken)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )
    cleaner = BasicCleaner(
        [
            {"format.decode_check": {"action": "drop"}},
            {"size.dimension_check": {"min_width": 8, "min_height": 8, "action": "review"}},
        ]
    )
    result = cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    full = result.export("full", str(tmp_path / "full.parquet"))
    clean = result.export("clean", str(tmp_path / "clean.parquet"))
    review = result.export("review", str(tmp_path / "review.parquet"))
    dropped = result.export("dropped", str(tmp_path / "dropped.parquet"))
    parameters = result.export("parameters", str(tmp_path / "parameters.parquet"))
    evaluations = result.export("evaluations", str(tmp_path / "evaluations.parquet"))
    preview = result.preview()

    assert full.count() == 3
    assert clean.count() == 1
    assert review.count() == 1
    assert dropped.count() == 1
    assert preview.restricted_count == 0
    assert {"image_id", "image_uri", "width", "height", "decode_error", "decode_ok"}.issubset(
        parameters.to_frame().columns
    )
    assert evaluations.count() == 3


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
    result = cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    output_path = result.preview_html(
        tmp_path / "preview.html",
        action="drop",
        caption_columns=["image_id"],
    )

    html = output_path.read_text(encoding="utf-8")
    assert output_path == tmp_path / "preview.html"
    assert "Cleaning Preview" in html
    assert "bad" in html
    assert "final_action: drop" not in html
