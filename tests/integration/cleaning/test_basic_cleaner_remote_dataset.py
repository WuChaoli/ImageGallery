from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset
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


def _image_bytes(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> bytes:
    Image.new("RGB", size, color=color).save(path)
    return path.read_bytes()


def test_basic_cleaner_runs_builtin_operators_on_s3_dataset(tmp_path: Path) -> None:
    storage = FakeS3Storage()
    ok_uri = storage.write_bytes(
        "images/ok.png",
        _image_bytes(tmp_path / "ok.png", (20, 20), (100, 120, 140)),
    )
    small_uri = storage.write_bytes(
        "images/small.png",
        _image_bytes(tmp_path / "small.png", (4, 4), (100, 120, 140)),
    )
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["img-1", "img-2"],
                "image_uri": [ok_uri, small_uri],
            }
        ),
        str(tmp_path / "raw.parquet"),
        storage=storage,
    )

    cleaner = BasicCleaner(
        [
            {"format.decode_check": {}},
            {"size.dimension_check": {"min_width": 10, "min_height": 10, "action": "review"}},
        ]
    )

    result = cleaner.run(dataset)

    parameter_table = pd.read_parquet(result._run_dir() / "tables" / "parameter_table.parquet")
    assert {"width", "height", "decode_ok", "decode_error"}.issubset(parameter_table.columns)
    assert result.result("format.decode_check")["decode_action"].tolist() == ["keep", "keep"]
    assert result.result("size.dimension_check")["dimension_action"].tolist() == ["keep", "review"]


def test_result_preview_html_embeds_s3_images_from_runtime_dataset(tmp_path: Path) -> None:
    storage = FakeS3Storage()
    ok_uri = storage.write_bytes(
        "images/ok.png",
        _image_bytes(tmp_path / "ok.png", (20, 20), (100, 120, 140)),
    )
    dataset = Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["img-1"],
                "image_uri": [ok_uri],
            }
        ),
        str(tmp_path / "raw.parquet"),
        storage=storage,
    )

    result = BasicCleaner([{"format.decode_check": {}}]).run(dataset)
    output_path = result.preview_html(
        tmp_path / "preview.html",
        operator_name="format.decode_check",
        actions="full",
    )

    html = output_path.read_text(encoding="utf-8")
    assert 'src="data:image/jpeg;base64,' in html
    assert 'src="s3://' not in html
    assert "Image read failed" not in html
