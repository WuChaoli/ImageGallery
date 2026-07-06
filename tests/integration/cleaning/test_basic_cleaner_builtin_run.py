from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


def _write_image(path: Path, size: tuple[int, int] = (20, 20)) -> None:
    image = Image.new("RGB", size, color=(100, 120, 140))
    for x in range(size[0]):
        for y in range(size[1]):
            if (x + y) % 2 == 0:
                image.putpixel((x, y), (180, 60, 90))
    image.save(path)


def test_basic_cleaner_runs_first_batch_builtin_operators(tmp_path: Path) -> None:
    ok_path = tmp_path / "ok.png"
    duplicate_path = tmp_path / "duplicate.png"
    small_path = tmp_path / "small.png"
    blank_path = tmp_path / "blank.png"
    broken_path = tmp_path / "broken.jpg"
    _write_image(ok_path, size=(32, 32))
    duplicate_path.write_bytes(ok_path.read_bytes())
    _write_image(small_path, size=(4, 4))
    Image.new("RGB", (32, 32), color=(255, 255, 255)).save(blank_path)
    broken_path.write_bytes(b"not an image")
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["ok", "dupe", "small", "blank", "bad"],
                "image_uri": [str(ok_path), str(duplicate_path), str(small_path), str(blank_path), str(broken_path)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )

    cleaner = BasicCleaner(
        [
            {"format.decode_check": {}},
            {"size.dimension_check": {"min_width": 10, "min_height": 10, "action": "drop"}},
            {"size.aspect_ratio_check": {}},
            {"size.megapixel_check": {"min_megapixels": 0.00001}},
            {"quality.blur_check": {"min_score": 0.0}},
            {"quality.brightness_check": {}},
            {"quality.contrast_check": {"min_score": 0.0}},
            {"content.blank_image_check": {}},
            {"duplicate.exact_duplicate_check": {}},
        ]
    )
    cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    rows = cleaner.export("full", str(tmp_path / "full.parquet")).to_frame().set_index("image_id")
    assert rows.loc["ok", "final_action"] == "keep"
    assert rows.loc["bad", "decode_action"] == "drop"
    assert rows.loc["small", "dimension_action"] == "drop"
    assert rows.loc["blank", "blank_action"] == "drop"
    assert rows.loc["dupe", "exact_duplicate_action"] == "drop"
    assert cleaner.preview().total_count == 5

    run_dir = next((tmp_path / "cleaning").iterdir())
    parameter_rows = pd.read_parquet(run_dir / "parameter_table.parquet")
    for column in [
        "aspect_ratio",
        "megapixels",
        "blur_score",
        "brightness_score",
        "contrast_score",
        "blank_score",
        "content_hash",
        "exact_duplicate_group_id",
        "exact_duplicate_count",
    ]:
        assert column in parameter_rows.columns
    assert (run_dir / "relations" / "duplicate_pairs.parquet").exists()
