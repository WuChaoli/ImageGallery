from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from image_gallery.dataset import Dataset
from image_gallery.storage.base import Storage
from image_gallery.storage.errors import ObjectNotFoundError


class FakeS3Storage(Storage):
    """测试用内存 storage，模拟 s3://bucket/object_path 读取。"""

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


def _write_image(
    path: Path,
    size: tuple[int, int] = (8, 6),
    color: tuple[int, int, int] = (10, 20, 30),
) -> bytes:
    Image.new("RGB", size, color=color).save(path)
    return path.read_bytes()


def test_dataset_reads_local_absolute_image_bytes_and_pil(tmp_path: Path) -> None:
    image_path = tmp_path / "local.png"
    image_bytes = _write_image(image_path, size=(9, 7))
    dataset = Dataset.write(
        pd.DataFrame([{"image_id": "img-1", "image_uri": str(image_path)}]),
        str(tmp_path / "raw.parquet"),
    )

    assert dataset.read_image_bytes(str(image_path)) == image_bytes
    image = dataset.read_image(str(image_path))

    assert image.size == (9, 7)
    assert image.format == "PNG"


def test_dataset_reads_file_uri_image(tmp_path: Path) -> None:
    image_path = tmp_path / "file-uri.png"
    image_bytes = _write_image(image_path)
    dataset = Dataset.write(
        pd.DataFrame([{"image_id": "img-1", "image_uri": image_path.as_uri()}]),
        str(tmp_path / "raw.parquet"),
    )

    assert dataset.read_image_bytes(image_path.as_uri()) == image_bytes
    assert dataset.read_image(image_path.as_uri()).size == (8, 6)


def test_dataset_reads_s3_image_through_bound_storage(tmp_path: Path) -> None:
    image_path = tmp_path / "remote.png"
    image_bytes = _write_image(image_path, size=(11, 5))
    storage = FakeS3Storage()
    image_uri = storage.write_bytes("images/remote.png", image_bytes)
    dataset = Dataset.write(
        pd.DataFrame([{"image_id": "img-1", "image_uri": image_uri}]),
        str(tmp_path / "raw.parquet"),
        storage=storage,
    )

    assert dataset.read_image_bytes(image_uri) == image_bytes
    assert dataset.read_image(image_uri).size == (11, 5)


def test_dataset_rejects_s3_image_without_storage(tmp_path: Path) -> None:
    dataset = Dataset.write(
        pd.DataFrame([{"image_id": "img-1", "image_uri": "s3://test-bucket/images/a.png"}]),
        str(tmp_path / "raw.parquet"),
    )

    with pytest.raises(ValueError, match="storage is required for s3 image_uri"):
        dataset.read_image_bytes("s3://test-bucket/images/a.png")


def test_dataset_batch_reading_keeps_success_and_failure_items(tmp_path: Path) -> None:
    ok_path = tmp_path / "ok.png"
    ok_bytes = _write_image(ok_path)
    missing_path = tmp_path / "missing.png"
    dataset = Dataset.write(
        pd.DataFrame(
            [
                {"image_id": "img-1", "image_uri": str(ok_path)},
                {"image_id": "img-2", "image_uri": str(missing_path)},
            ]
        ),
        str(tmp_path / "raw.parquet"),
    )

    byte_results = dataset.read_image_bytes_batch([str(ok_path), str(missing_path)])
    image_results = dataset.read_image_batch([str(ok_path), str(missing_path)])

    assert byte_results[0].ok is True
    assert byte_results[0].data == ok_bytes
    assert byte_results[1].ok is False
    assert byte_results[1].data is None
    assert "missing.png" in str(byte_results[1].error)
    assert image_results[0].ok is True
    assert image_results[0].image is not None
    assert image_results[1].ok is False


def test_dataset_iter_images_preserves_dataset_order_and_selected_columns(tmp_path: Path) -> None:
    first_path = tmp_path / "first.png"
    second_path = tmp_path / "second.png"
    _write_image(first_path)
    _write_image(second_path)
    dataset = Dataset.write(
        pd.DataFrame(
            [
                {"image_id": "img-2", "image_uri": str(second_path), "label": "second", "ignored": "b"},
                {"image_id": "img-1", "image_uri": str(first_path), "label": "first", "ignored": "a"},
            ]
        ),
        str(tmp_path / "raw.parquet"),
    )

    images = list(dataset.iter_images(columns=["label"]))

    assert [image.image_id for image in images] == ["img-2", "img-1"]
    assert [image.image_uri for image in images] == [str(second_path), str(first_path)]
    assert images[0].row == {"image_id": "img-2", "image_uri": str(second_path), "label": "second"}
    assert images[0].read_bytes() == second_path.read_bytes()
    assert images[1].read_image().size == (8, 6)
