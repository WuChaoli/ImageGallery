from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


def _tiny_dataset(tmp_path: Path) -> Dataset:
    first = tmp_path / "one.png"
    second = tmp_path / "two.png"
    with Image.new("RGB", (2, 2), color=(255, 0, 0)) as image:
        image.save(first)
    with Image.new("RGB", (2, 2), color=(0, 255, 0)) as image:
        image.save(second)

    return Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["img-1", "img-2"],
                "image_uri": [str(first), str(second)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )


def test_basic_cleaner_run_returns_result_and_hides_process_outputs(tmp_path: Path) -> None:
    dataset = _tiny_dataset(tmp_path)
    result = BasicCleaner([{"format.decode_check": {}}]).run(dataset, label="smoke")

    assert result.status() in {"completed", "running"}
    assert not (tmp_path / "parameter_table.parquet").exists()
