from pathlib import Path

import pandas as pd
import pytest

from image_gallery.dataset import Dataset


def test_dataset_write_and_read_parquet(tmp_path: Path) -> None:
    output_path = str(tmp_path / "raw.parquet")
    frame = pd.DataFrame(
        [
            {"image_id": "img-1", "image_uri": "/tmp/a.jpg", "width": 10, "height": 20},
            {"image_id": "img-2", "image_uri": "/tmp/b.jpg", "width": 30, "height": 40},
        ]
    )

    dataset = Dataset.write(frame, output_path)

    assert dataset.dataset_path == output_path
    assert dataset.count() == 2
    assert dataset.preview(limit=1).to_dict("records") == [
        {"image_id": "img-1", "image_uri": "/tmp/a.jpg", "width": 10, "height": 20}
    ]


def test_dataset_load_reads_existing_file(tmp_path: Path) -> None:
    output_path = str(tmp_path / "raw.parquet")
    pd.DataFrame([{"image_id": "img-1", "image_uri": "/tmp/a.jpg"}]).to_parquet(output_path, index=False)

    dataset = Dataset.load(output_path)

    assert dataset.count() == 1


def test_dataset_does_not_expose_from_path_alias() -> None:
    assert not hasattr(Dataset, "from_path")


def test_dataset_load_accepts_path_object(tmp_path: Path) -> None:
    output_path = tmp_path / "raw.parquet"
    pd.DataFrame([{"image_id": "img-1", "image_uri": "/tmp/a.jpg"}]).to_parquet(output_path, index=False)

    dataset = Dataset.load(output_path)

    assert dataset.dataset_path == str(output_path)
    assert dataset.count() == 1


def test_dataset_scan_selects_columns_and_filters_rows(tmp_path: Path) -> None:
    output_path = str(tmp_path / "raw.parquet")
    Dataset.write(
        pd.DataFrame(
            [
                {"image_id": "img-1", "image_uri": "/tmp/a.jpg", "import_status": "imported"},
                {"image_id": "img-2", "image_uri": "/tmp/b.jpg", "import_status": "failed"},
            ]
        ),
        output_path,
    )

    frame = Dataset.load(output_path).scan(columns=["image_id"], filters={"import_status": "imported"})

    assert frame.to_dict("records") == [{"image_id": "img-1"}]


def test_dataset_validate_readable_rejects_missing_file(tmp_path: Path) -> None:
    missing = Dataset.load(str(tmp_path / "missing.parquet"))

    with pytest.raises(FileNotFoundError):
        missing.validate_readable()
