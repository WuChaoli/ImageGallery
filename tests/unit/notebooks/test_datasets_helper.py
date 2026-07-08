from pathlib import Path

import pandas as pd
import pytest
from notebooks._helpers.datasets import (
    get_default_minio_sample_1000_raw_path,
    load_default_minio_sample_1000_dataset,
    load_default_minio_sample_1000_frame,
)


def test_get_default_minio_sample_1000_raw_path_points_to_expected_location() -> None:
    expected = Path("datasets/sample_1000/raw.parquet")
    assert get_default_minio_sample_1000_raw_path().as_posix().endswith(expected.as_posix())


def test_load_default_minio_sample_1000_frame_reads_existing_parquet() -> None:
    raw_path = get_default_minio_sample_1000_raw_path()
    if not raw_path.exists():
        pytest.skip(f"sample raw dataset not found: {raw_path}")

    frame = load_default_minio_sample_1000_frame()

    assert isinstance(frame, pd.DataFrame)
    assert "image_id" in frame.columns
    assert "image_uri" in frame.columns


def test_load_default_minio_sample_1000_dataset_requires_storage_backing() -> None:
    raw_path = get_default_minio_sample_1000_raw_path()
    if not raw_path.exists():
        pytest.skip(f"sample raw dataset not found: {raw_path}")

    dataset = load_default_minio_sample_1000_dataset()

    assert str(dataset.dataset_path).endswith("sample_1000/raw.parquet")
    assert dataset.storage is not None
