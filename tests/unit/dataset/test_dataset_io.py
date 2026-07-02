from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset


def test_dataset_write_and_read_parquet(tmp_path: Path) -> None:
    output_uri = str(tmp_path / "raw.parquet")
    frame = pd.DataFrame(
        [
            {"image_id": "img-1", "image_uri": "/tmp/a.jpg", "width": 10, "height": 20},
            {"image_id": "img-2", "image_uri": "/tmp/b.jpg", "width": 30, "height": 40},
        ]
    )

    dataset = Dataset.write(frame, output_uri)

    assert dataset.dataset_uri == output_uri
    assert dataset.count() == 2
    assert dataset.preview(limit=1).to_dict("records") == [
        {"image_id": "img-1", "image_uri": "/tmp/a.jpg", "width": 10, "height": 20}
    ]


def test_dataset_from_uri_reads_existing_file(tmp_path: Path) -> None:
    output_uri = str(tmp_path / "raw.parquet")
    pd.DataFrame([{"image_id": "img-1", "image_uri": "/tmp/a.jpg"}]).to_parquet(output_uri, index=False)

    dataset = Dataset.from_uri(output_uri)

    assert dataset.count() == 1
