import pandas as pd
import pytest

from image_gallery.schemas import RawDatasetSchema, validate_raw_dataset


def _raw_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "image_id": "img-1",
        "source_uri": "/external/a.jpg",
        "source_type": "local_directory",
        "source_file_name": "a.jpg",
        "storage_name": "local_main",
        "image_uri": "/managed/a.jpg",
        "file_size_bytes": 3,
        "image_content_hash": "sha256:abc",
        "file_extension": ".jpg",
        "mime_type": "image/jpeg",
        "image_format": "JPEG",
        "width": 10,
        "height": 20,
        "pixel_count": 200,
        "aspect_ratio": 0.5,
        "orientation": "portrait",
        "channels": 3,
        "color_mode": "RGB",
        "has_alpha": False,
        "animated": False,
        "frame_count": 1,
        "icc_profile_present": False,
        "dpi_x": None,
        "dpi_y": None,
        "exif_orientation": None,
        "exif_datetime": None,
        "camera_make": None,
        "camera_model": None,
        "gps_present": False,
        "gps_latitude": None,
        "gps_longitude": None,
        "import_status": "imported",
        "imported_at": "2026-07-02T00:00:00Z",
        "schema_version": "raw.v1",
        "tags": ["scene/indoor", "scene/kitchen/cook", "quality/blur"],
    }
    row.update(overrides)
    return row


def test_validate_raw_dataset_accepts_minimal_fields() -> None:
    frame = pd.DataFrame([_raw_row()])

    validate_raw_dataset(frame)


def test_validate_raw_dataset_rejects_missing_required_column() -> None:
    frame = pd.DataFrame([{"image_id": "img-1"}])

    with pytest.raises(ValueError, match="missing required raw dataset columns"):
        validate_raw_dataset(frame)


def test_raw_dataset_schema_exposes_schema_version() -> None:
    assert RawDatasetSchema.version == "raw.v1"


def test_validate_raw_dataset_requires_schema_version_column() -> None:
    row = _raw_row()
    row.pop("schema_version")
    frame = pd.DataFrame([row])

    with pytest.raises(ValueError, match="schema_version"):
        validate_raw_dataset(frame)


def test_validate_raw_dataset_accepts_empty_tags() -> None:
    frame = pd.DataFrame([_raw_row(tags=[])])

    validate_raw_dataset(frame)


@pytest.mark.parametrize(
    ("tags", "expected_exception"),
    [
        (None, TypeError),
        ("scene/indoor", TypeError),
        ([123], ValueError),
        ([""], ValueError),
        (["/scene"], ValueError),
        (["scene/"], ValueError),
        (["scene//indoor"], ValueError),
    ],
)
def test_validate_raw_dataset_rejects_invalid_tags(tags: object, expected_exception: type[Exception]) -> None:
    frame = pd.DataFrame([_raw_row(tags=tags)])

    with pytest.raises(expected_exception, match="invalid raw dataset tags"):
        validate_raw_dataset(frame)
