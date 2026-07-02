from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset


def test_dataset_fingerprint_is_stable_for_same_content(tmp_path: Path) -> None:
    first_path = str(tmp_path / "first.parquet")
    second_path = str(tmp_path / "second.parquet")
    frame = pd.DataFrame([{"image_id": "img-1", "image_uri": "/tmp/a.jpg"}])
    frame.to_parquet(first_path, index=False)
    frame.to_parquet(second_path, index=False)

    assert Dataset.from_path(first_path).fingerprint() == Dataset.from_path(second_path).fingerprint()
