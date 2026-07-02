import pandas as pd
import pytest

from image_gallery.schemas import RawDatasetSchema, validate_raw_dataset


def test_validate_raw_dataset_accepts_minimal_fields() -> None:
    frame = pd.DataFrame(
        [
            {
                "image_id": "img-1",
                "source_uri": "/external/a.jpg",
                "source_type": "local_directory",
                "source_file_name": "a.jpg",
                "storage_name": "local_main",
                "image_uri": "/managed/a.jpg",
                "file_size_bytes": 3,
                "checksum": "sha256:abc",
                "image_format": "JPEG",
                "width": 10,
                "height": 20,
                "channels": 3,
                "color_mode": "RGB",
                "import_status": "imported",
                "imported_at": "2026-07-02T00:00:00Z",
                "schema_version": "raw.v1",
            }
        ]
    )

    validate_raw_dataset(frame)


def test_validate_raw_dataset_rejects_missing_required_column() -> None:
    frame = pd.DataFrame([{"image_id": "img-1"}])

    with pytest.raises(ValueError, match="missing required raw dataset columns"):
        validate_raw_dataset(frame)


def test_raw_dataset_schema_exposes_schema_version() -> None:
    assert RawDatasetSchema.version == "raw.v1"


def test_validate_raw_dataset_requires_schema_version_column() -> None:
    frame = pd.DataFrame(
        [
            {
                "image_id": "img-1",
                "source_uri": "/external/a.jpg",
                "source_type": "local_directory",
                "source_file_name": "a.jpg",
                "storage_name": "local_main",
                "image_uri": "/managed/a.jpg",
                "file_size_bytes": 3,
                "checksum": "sha256:abc",
                "image_format": "JPEG",
                "width": 10,
                "height": 20,
                "channels": 3,
                "color_mode": "RGB",
                "import_status": "imported",
                "imported_at": "2026-07-02T00:00:00Z",
            }
        ]
    )

    with pytest.raises(ValueError, match="schema_version"):
        validate_raw_dataset(frame)
