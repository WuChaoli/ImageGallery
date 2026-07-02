from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset


def test_dataset_fingerprint_is_stable_for_same_content(tmp_path: Path) -> None:
    first_uri = str(tmp_path / "first.parquet")
    second_uri = str(tmp_path / "second.parquet")
    frame = pd.DataFrame([{"image_id": "img-1", "image_uri": "/tmp/a.jpg"}])
    frame.to_parquet(first_uri, index=False)
    frame.to_parquet(second_uri, index=False)

    assert Dataset.from_uri(first_uri).fingerprint() == Dataset.from_uri(second_uri).fingerprint()
