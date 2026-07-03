from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.dataset import Dataset
from image_gallery.operators.backends.base import BackendOperatorRequest
from image_gallery.operators.backends.pillow_backend import PillowMetadataBackend, read_image_metadata
from image_gallery.storage.base import Storage
from image_gallery.storage.errors import ObjectNotFoundError


class FakeS3Storage(Storage):
    storage_name = "fake_s3"

    def __init__(self, bucket: str = "test-bucket") -> None:
        self.bucket = bucket
        self.objects: dict[str, bytes] = {}

    def _write_bytes(self, object_path: str, data: bytes, overwrite: bool = False) -> str:
        self.objects[object_path] = data
        return self.make_image_uri(object_path)

    def _read_bytes(self, object_path: str) -> bytes:
        if object_path not in self.objects:
            raise ObjectNotFoundError(f"object not found: {object_path}")
        return self.objects[object_path]

    def exists(self, object_path: str) -> bool:
        return object_path in self.objects

    def delete(self, object_path: str) -> None:
        if object_path not in self.objects:
            raise ObjectNotFoundError(f"object not found: {object_path}")
        del self.objects[object_path]

    def copy(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
        self.objects[dst_object_path] = self.read_bytes(src_object_path)
        return self.make_image_uri(dst_object_path)

    def move(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
        image_uri = self.copy(src_object_path, dst_object_path, overwrite)
        self.delete(src_object_path)
        return image_uri

    def make_image_uri(self, object_path: str) -> str:
        return f"s3://{self.bucket}/{object_path}"


def _write_image(path: Path, size: tuple[int, int] = (12, 8)) -> None:
    Image.new("RGB", size, color=(100, 120, 140)).save(path)


def test_read_image_metadata_returns_basic_fields(tmp_path: Path) -> None:
    image_path = tmp_path / "a.png"
    _write_image(image_path)
    dataset = Dataset.write(
        pd.DataFrame([{"image_id": "img-1", "image_uri": str(image_path)}]),
        str(tmp_path / "raw.parquet"),
    )

    metadata = read_image_metadata(next(dataset.iter_images()))

    assert metadata["width"] == 12
    assert metadata["height"] == 8
    assert metadata["format"] == "PNG"
    assert metadata["decode_ok"] is True
    assert metadata["decode_error"] == ""


def test_pillow_metadata_backend_records_decode_errors_without_stopping(tmp_path: Path) -> None:
    image_path = tmp_path / "a.png"
    broken_path = tmp_path / "broken.jpg"
    _write_image(image_path)
    broken_path.write_bytes(b"not an image")
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["img-1", "img-2"],
                "image_uri": [str(image_path), str(broken_path)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )
    parameter_table = dataset.to_frame()
    backend = PillowMetadataBackend()

    result = backend.compute_parameters(
        dataset,
        parameter_table,
        [
            BackendOperatorRequest("format.decode_check", ["decode_ok", "decode_error"], {}, "a"),
            BackendOperatorRequest("size.dimension_check", ["width", "height"], {}, "b"),
        ],
        tmp_path / "artifacts",
    )

    rows = result.parameter_updates.sort_values("image_id").to_dict(orient="records")
    assert rows[0]["decode_ok"] is True
    assert rows[0]["width"] == 12
    assert rows[1]["decode_ok"] is False
    assert rows[1]["decode_error"]


def test_pillow_metadata_backend_reads_s3_images_through_dataset_storage(tmp_path: Path) -> None:
    image_path = tmp_path / "remote.png"
    _write_image(image_path, size=(13, 9))
    storage = FakeS3Storage()
    image_uri = storage.write_bytes("images/remote.png", image_path.read_bytes())
    dataset = Dataset.write(
        pd.DataFrame({"image_id": ["img-1"], "image_uri": [image_uri]}),
        str(tmp_path / "raw.parquet"),
        storage=storage,
    )

    result = PillowMetadataBackend().compute_parameters(
        dataset,
        dataset.to_frame(),
        [BackendOperatorRequest("size.dimension_check", ["width", "height"], {}, "a")],
        tmp_path / "artifacts",
    )

    row = result.parameter_updates.iloc[0].to_dict()
    assert row["image_id"] == "img-1"
    assert row["width"] == 13
    assert row["height"] == 9
    assert row["decode_ok"] is True
