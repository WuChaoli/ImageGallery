from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


def _write_image(path: Path, size: tuple[int, int] = (20, 20)) -> None:
    Image.new("RGB", size, color=(100, 120, 140)).save(path)


def test_basic_cleaner_runs_builtin_v3_decode_and_dimension_operators(tmp_path: Path) -> None:
    ok_path = tmp_path / "ok.png"
    small_path = tmp_path / "small.png"
    broken_path = tmp_path / "broken.jpg"
    _write_image(ok_path)
    _write_image(small_path, size=(4, 4))
    broken_path.write_bytes(b"not an image")
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["ok", "small", "bad"],
                "image_uri": [str(ok_path), str(small_path), str(broken_path)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )

    cleaner = BasicCleaner(
        [
            {"format.decode_check": {}},
            {"size.dimension_check": {"min_width": 10, "min_height": 10, "action": "review"}},
        ]
    )
    cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    rows = cleaner.export("full", str(tmp_path / "full.parquet")).to_frame().set_index("image_id")
    assert rows.loc["ok", "final_action"] == "keep"
    assert rows.loc["small", "final_action"] == "review"
    assert rows.loc["bad", "final_action"] == "drop"
    assert cleaner.preview().total_count == 3
    assert cleaner.preview().review_count == 1
    assert cleaner.preview().dropped_count == 1
    assert cleaner.result("format.decode_check")["decode_action"].tolist() == ["keep", "keep", "drop"]
    assert cleaner.result("size.dimension_check")["dimension_action"].tolist() == ["keep", "review", "review"]
