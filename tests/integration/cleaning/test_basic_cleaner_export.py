from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (16, 16), color=color).save(path)


def test_basic_cleaner_exports_builtin_views_and_preserves_counts(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    duplicate = tmp_path / "duplicate.png"
    unique = tmp_path / "unique.png"
    _write_image(first, (10, 20, 30))
    duplicate.write_bytes(first.read_bytes())
    _write_image(unique, (200, 210, 220))
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["img-1", "img-2", "img-3"],
                "image_uri": [str(first), str(duplicate), str(unique)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )
    cleaner = BasicCleaner(
        [
            {"format.decode_check": {}},
            {"duplicate.exact_duplicate_check": {"action": "drop"}},
        ]
    )
    cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    full = cleaner.export("full", str(tmp_path / "full.parquet"))
    clean = cleaner.export("clean", str(tmp_path / "clean.parquet"))
    review = cleaner.export("review", str(tmp_path / "review.parquet"))
    dropped = cleaner.export("dropped", str(tmp_path / "dropped.parquet"))
    parameters = cleaner.export("parameters", str(tmp_path / "parameters.parquet"))
    evaluations = cleaner.export("evaluations", str(tmp_path / "evaluations.parquet"))
    preview = cleaner.preview()

    assert full.count() == 3
    assert clean.count() + review.count() + dropped.count() + preview.restricted_count == full.count()
    assert dropped.count() == 2
    assert parameters.to_frame()["content_hash"].nunique() == 2
    assert evaluations.count() == 3
