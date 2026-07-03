from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


def test_basic_cleaner_quality_rerun_updates_evaluation_only_policy(tmp_path: Path) -> None:
    image_path = tmp_path / "flat.png"
    Image.new("RGB", (16, 16), color=(128, 128, 128)).save(image_path)
    dataset = Dataset.write(
        pd.DataFrame({"image_id": ["img-1"], "image_uri": [str(image_path)]}),
        str(tmp_path / "raw.parquet"),
    )
    cleaner = BasicCleaner(
        [
            {"quality.blur_check": {"threshold": 1.0, "action": "review"}},
            {"quality.brightness_check": {"min_threshold": 20.0, "max_threshold": 235.0}},
            {"quality.contrast_check": {"threshold": 1.0}},
        ]
    )
    cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    assert cleaner.preview().review_count == 1

    cleaner.rerun([{"quality.blur_check": {"threshold": -1.0, "action": "review"}}])

    assert cleaner.preview().review_count == 1
    assert cleaner.result("quality.blur_check")["blur_action"].tolist() == ["keep"]
    assert cleaner.result("quality.contrast_check")["contrast_action"].tolist() == ["review"]
