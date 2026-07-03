from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.dataset import Dataset
from image_gallery.operators.backends.base import BackendOperatorRequest
from image_gallery.operators.backends.hash_backend import (
    ImageHashBackend,
    assign_exact_duplicate_groups,
    compute_content_hash,
    compute_phash,
)
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


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    Image.new("RGB", (12, 12), color=color).save(path)


def test_hash_functions_are_stable_for_same_file(tmp_path: Path) -> None:
    image_path = tmp_path / "a.png"
    _write_image(image_path, (10, 20, 30))
    dataset = Dataset.write(
        pd.DataFrame([{"image_id": "img-1", "image_uri": str(image_path)}]),
        str(tmp_path / "raw.parquet"),
    )
    image = next(dataset.iter_images())

    assert compute_content_hash(image) == compute_content_hash(image)
    assert compute_phash(image) == compute_phash(image)
    assert len(compute_phash(image)) == 16


def test_assign_exact_duplicate_groups_marks_only_duplicates() -> None:
    frame = pd.DataFrame(
        {
            "image_id": ["img-1", "img-2", "img-3"],
            "content_hash": ["same", "same", "other"],
        }
    )

    result = assign_exact_duplicate_groups(frame)

    assert result["exact_duplicate_group_id"].tolist() == ["exact-000001", "exact-000001", ""]


def test_image_hash_backend_computes_duplicate_groups(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    third = tmp_path / "third.png"
    _write_image(first, (10, 20, 30))
    second.write_bytes(first.read_bytes())
    _write_image(third, (200, 210, 220))
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["img-1", "img-2", "img-3"],
                "image_uri": [str(first), str(second), str(third)],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )

    result = ImageHashBackend().compute_parameters(
        dataset,
        dataset.to_frame(),
        [BackendOperatorRequest("duplicate.exact_duplicate_check", ["content_hash", "phash"], {}, "a")],
        tmp_path / "artifacts",
    )

    rows = result.parameter_updates.sort_values("image_id").to_dict(orient="records")
    assert rows[0]["content_hash"] == rows[1]["content_hash"]
    assert rows[0]["exact_duplicate_group_id"] == "exact-000001"
    assert rows[2]["exact_duplicate_group_id"] == ""


def test_image_hash_backend_reads_s3_images_through_dataset_storage(tmp_path: Path) -> None:
    image_path = tmp_path / "remote.png"
    _write_image(image_path, (10, 20, 30))
    storage = FakeS3Storage()
    image_uri = storage.write_bytes("images/remote.png", image_path.read_bytes())
    dataset = Dataset.write(
        pd.DataFrame({"image_id": ["img-1"], "image_uri": [image_uri]}),
        str(tmp_path / "raw.parquet"),
        storage=storage,
    )

    result = ImageHashBackend().compute_parameters(
        dataset,
        dataset.to_frame(),
        [BackendOperatorRequest("duplicate.exact_duplicate_check", ["content_hash", "phash"], {}, "a")],
        tmp_path / "artifacts",
    )

    row = result.parameter_updates.iloc[0].to_dict()
    assert row["image_id"] == "img-1"
    assert row["content_hash"]
    assert len(row["phash"]) == 16
