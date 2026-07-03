from pathlib import Path

import pandas as pd
from PIL import Image, ImageFilter

from image_gallery.dataset import Dataset
from image_gallery.operators.backends.base import BackendOperatorRequest
from image_gallery.operators.backends.opencv_backend import (
    OpenCVQualityBackend,
    compute_blur_score,
    compute_brightness_score,
    compute_contrast_score,
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


def _write_checker(path: Path, size: int = 32) -> None:
    image = Image.new("L", (size, size), color=0)
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            pixels[x, y] = 255 if (x + y) % 2 == 0 else 0
    image.convert("RGB").save(path)


def _single_image(tmp_path: Path, image_path: Path) -> object:
    dataset = Dataset.write(
        pd.DataFrame([{"image_id": image_path.stem, "image_uri": str(image_path)}]),
        str(tmp_path / f"{image_path.stem}.parquet"),
    )
    return next(dataset.iter_images())


def test_quality_scores_reflect_basic_image_properties(tmp_path: Path) -> None:
    sharp_path = tmp_path / "sharp.png"
    blurry_path = tmp_path / "blurry.png"
    dark_path = tmp_path / "dark.png"
    _write_checker(sharp_path)
    Image.open(sharp_path).filter(ImageFilter.GaussianBlur(radius=3)).save(blurry_path)
    Image.new("RGB", (16, 16), color=(5, 5, 5)).save(dark_path)
    sharp = _single_image(tmp_path, sharp_path)
    blurry = _single_image(tmp_path, blurry_path)
    dark = _single_image(tmp_path, dark_path)

    assert compute_blur_score(sharp) > compute_blur_score(blurry)
    assert compute_brightness_score(dark) < 10
    assert compute_contrast_score(sharp) > compute_contrast_score(dark)


def test_opencv_quality_backend_computes_requested_columns(tmp_path: Path) -> None:
    image_path = tmp_path / "image.png"
    _write_checker(image_path)
    dataset = Dataset.write(
        pd.DataFrame({"image_id": ["img-1"], "image_uri": [str(image_path)]}),
        str(tmp_path / "raw.parquet"),
    )
    backend = OpenCVQualityBackend()

    result = backend.compute_parameters(
        dataset,
        dataset.to_frame(),
        [
            BackendOperatorRequest("quality.blur_check", ["blur_score"], {}, "a"),
            BackendOperatorRequest("quality.brightness_check", ["brightness_score"], {}, "b"),
            BackendOperatorRequest("quality.contrast_check", ["contrast_score"], {}, "c"),
        ],
        tmp_path / "artifacts",
    )

    row = result.parameter_updates.iloc[0].to_dict()
    assert row["image_id"] == "img-1"
    assert row["blur_score"] > 0
    assert row["brightness_score"] > 0
    assert row["contrast_score"] > 0


def test_opencv_quality_backend_reads_s3_images_through_dataset_storage(tmp_path: Path) -> None:
    image_path = tmp_path / "remote.png"
    _write_checker(image_path)
    storage = FakeS3Storage()
    image_uri = storage.write_bytes("images/remote.png", image_path.read_bytes())
    dataset = Dataset.write(
        pd.DataFrame({"image_id": ["img-1"], "image_uri": [image_uri]}),
        str(tmp_path / "raw.parquet"),
        storage=storage,
    )

    result = OpenCVQualityBackend().compute_parameters(
        dataset,
        dataset.to_frame(),
        [
            BackendOperatorRequest("quality.blur_check", ["blur_score"], {}, "a"),
            BackendOperatorRequest("quality.brightness_check", ["brightness_score"], {}, "b"),
            BackendOperatorRequest("quality.contrast_check", ["contrast_score"], {}, "c"),
        ],
        tmp_path / "artifacts",
    )

    row = result.parameter_updates.iloc[0].to_dict()
    assert row["blur_score"] > 0
    assert row["brightness_score"] > 0
    assert row["contrast_score"] > 0
