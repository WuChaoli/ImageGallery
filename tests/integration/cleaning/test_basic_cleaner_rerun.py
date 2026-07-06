from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


def test_basic_cleaner_dimension_rerun_updates_evaluation_only_policy(tmp_path: Path) -> None:
    ok_path = tmp_path / "ok.png"
    small_path = tmp_path / "small.png"
    Image.new("RGB", (16, 16), color=(128, 128, 128)).save(ok_path)
    Image.new("RGB", (4, 4), color=(128, 128, 128)).save(small_path)
    dataset = Dataset.write(
        pd.DataFrame({"image_id": ["ok", "small"], "image_uri": [str(ok_path), str(small_path)]}),
        str(tmp_path / "raw.parquet"),
    )
    cleaner = BasicCleaner(
        [
            {"size.dimension_check": {"min_width": 8, "min_height": 8, "action": "review"}},
        ]
    )
    cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    assert cleaner.preview().review_count == 1
    before_parameters = cleaner.export("parameters", str(tmp_path / "parameters_before.parquet")).to_frame()

    cleaner.rerun([{"size.dimension_check": {"min_width": 1, "min_height": 1, "action": "review"}}])

    assert cleaner.preview().review_count == 0
    assert cleaner.result("size.dimension_check")["dimension_action"].tolist() == ["keep", "keep"]
    after_parameters = cleaner.export("parameters", str(tmp_path / "parameters_after.parquet")).to_frame()
    assert before_parameters.equals(after_parameters)
