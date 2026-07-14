from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


def test_basic_cleaner_minimal_run_writes_v3_outputs(tmp_path: Path) -> None:
    image_path = tmp_path / "image.png"
    Image.new("RGB", (8, 8), color=(100, 120, 140)).save(image_path)
    dataset = Dataset.write(
        pd.DataFrame({"image_id": ["img-1"], "image_uri": [str(image_path)]}),
        str(tmp_path / "raw.parquet"),
    )

    cleaner = BasicCleaner([{"decode": {}}])
    result = cleaner.run(dataset)

    assert result.preview().clean_count == 1
    assert result.export("clean", str(tmp_path / "clean.parquet")).count() == 1
