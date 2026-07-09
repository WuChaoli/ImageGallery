# Dataset Image Reading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Dataset-native image reading so local and `s3://...` images can flow through BasicCleaner and built-in backends without notebook-side materialization.

**Architecture:** Dataset owns lightweight `image_uri` parsing, image bytes/PIL reading, batch reading, and ordered `DatasetImage` iteration. BasicCleaner keeps its orchestration role unchanged; built-in backends switch from local-path reads to Dataset image APIs. Fastdup remains outside this implementation because its local-file input normalization is a separate backend concern.

**Tech Stack:** Python 3.10, pandas, Pillow, NumPy/OpenCV optional backend, ImageGallery `Dataset`, `Storage`, `BasicCleaner`, pytest.

---

## File Structure

- Modify `src/image_gallery/dataset/dataset.py`: add optional storage dependency, image URI parsing, bytes/PIL read methods, batch result dataclasses, and `DatasetImage`.
- Modify `src/image_gallery/dataset/__init__.py`: export new Dataset image helper types.
- Create `tests/unit/dataset/test_image_reading.py`: cover local, `file://`, `s3://`, batch, and ordered iteration behavior.
- Modify `src/image_gallery/operators/backends/pillow_backend.py`: read image metadata through `DatasetImage`.
- Modify `src/image_gallery/operators/backends/opencv_backend.py`: compute quality metrics from PIL/NumPy arrays instead of local paths.
- Modify `src/image_gallery/operators/backends/hash_backend.py`: compute content hash from bytes and perceptual hash from PIL images.
- Modify `tests/unit/operators/test_pillow_backend.py`: add fake storage `s3://...` backend test while keeping local tests.
- Modify `tests/unit/operators/test_opencv_backend.py`: add fake storage `s3://...` backend test while keeping local tests.
- Modify `tests/unit/operators/test_hash_backend.py`: add fake storage `s3://...` backend test while keeping local tests.
- Create `tests/integration/cleaning/test_basic_cleaner_remote_dataset.py`: verify BasicCleaner can run built-in basic operators against a storage-backed `s3://...` Dataset.
- Modify `docs/superpowers/specs/2026-07-03-operators-notebook-validation-design.md`: remove the old limitation that MinIO images must be materialized before operators can run.

## Task 1: Dataset Image Reading API

**Files:**
- Modify: `src/image_gallery/dataset/dataset.py`
- Modify: `src/image_gallery/dataset/__init__.py`
- Create: `tests/unit/dataset/test_image_reading.py`

- [ ] **Step 1: Write failing Dataset image reading tests**

Create `tests/unit/dataset/test_image_reading.py`:

```python
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


def _write_image(path: Path, size: tuple[int, int] = (8, 6), color: tuple[int, int, int] = (10, 20, 30)) -> bytes:
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
```

- [ ] **Step 2: Run Dataset image tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/dataset/test_image_reading.py -q
```

Expected: FAIL because `Dataset.write(..., storage=...)`, `read_image_bytes`, `read_image`, `read_image_bytes_batch`, `read_image_batch`, and `iter_images` do not exist yet.

- [ ] **Step 3: Implement Dataset image reading types and methods**

Modify `src/image_gallery/dataset/dataset.py`. Add imports near the top:

```python
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from urllib.parse import unquote, urlparse

import pandas as pd
from PIL import Image

from image_gallery.dataset.fingerprint import dataframe_fingerprint
from image_gallery.storage.base import Storage
from image_gallery.storage.uri import file_image_uri_to_path
```

Add helper dataclasses above `class Dataset`:

```python
@dataclass(frozen=True)
class DatasetImageBytesReadResult:
    """图片 bytes 批量读取结果，单张失败不影响整批。"""

    image_uri: str
    ok: bool
    data: bytes | None = None
    error: str | None = None


@dataclass(frozen=True)
class DatasetImageReadResult:
    """图片对象批量读取结果，单张失败不影响整批。"""

    image_uri: str
    ok: bool
    image: Image.Image | None = None
    error: str | None = None


@dataclass(frozen=True)
class ParsedImageUri:
    """Dataset 内部使用的图片地址解析结果。"""

    kind: str
    image_uri: str
    local_path: Path | None = None
    bucket: str | None = None
    object_path: str | None = None


@dataclass(frozen=True)
class DatasetImage:
    """Dataset 中按行枚举出的图片对象。"""

    image_id: str
    image_uri: str
    row: dict[str, object]
    dataset: "Dataset"

    def read_bytes(self) -> bytes:
        """读取当前图片 bytes。"""
        return self.dataset.read_image_bytes(self.image_uri)

    def read_image(self) -> Image.Image:
        """读取当前图片为 Pillow Image。"""
        return self.dataset.read_image(self.image_uri)
```

Change the `Dataset` dataclass fields and constructors:

```python
@dataclass(frozen=True)
class Dataset:
    """数据集文件的轻量封装，不表达 raw、clean、dropped、full 阶段语义。"""

    # dataset_path 是数据集文件路径，当前阶段主要支持本地 Parquet/CSV/JSONL。
    dataset_path: str
    # format 是由文件扩展名推导出的数据集格式，用于选择 Pandas 读写方法。
    format: str = "parquet"
    # storage 是可选图片对象读取依赖；本地路径不需要 storage。
    storage: Storage | None = field(default=None, compare=False, repr=False)

    @classmethod
    def from_path(cls, dataset_path: str, storage: Storage | None = None) -> "Dataset":
        """从已有数据集路径创建 Dataset 对象，不立即读取文件内容。"""
        return cls(dataset_path=dataset_path, format=_format_from_path(dataset_path), storage=storage)

    @classmethod
    def write(cls, data: pd.DataFrame, output_path: str, storage: Storage | None = None) -> "Dataset":
        """把 DataFrame 写出为数据集文件，并返回对应 Dataset 对象。"""
        resolved_output_path = Path(output_path)
        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
        file_format = _format_from_path(output_path)
        if file_format == "parquet":
            data.to_parquet(resolved_output_path, index=False)
        elif file_format == "csv":
            data.to_csv(resolved_output_path, index=False)
        elif file_format == "jsonl":
            data.to_json(resolved_output_path, orient="records", lines=True, force_ascii=False)
        else:
            raise ValueError(f"unsupported dataset format: {file_format}")
        return cls(dataset_path=output_path, format=file_format, storage=storage)
```

Add methods inside `Dataset`, after `to_frame()`:

```python
    def read_image_bytes(self, image_uri: str) -> bytes:
        """根据 image_uri 读取图片 bytes。"""
        parsed = _parse_image_uri(image_uri)
        if parsed.kind == "local":
            if parsed.local_path is None:
                raise ValueError(f"local image_uri parsed without path: {image_uri}")
            return parsed.local_path.read_bytes()
        if parsed.kind == "s3":
            if self.storage is None:
                raise ValueError(f"storage is required for s3 image_uri: {image_uri}")
            if parsed.object_path is None:
                raise ValueError(f"s3 image_uri parsed without object_path: {image_uri}")
            return self.storage.read_bytes(parsed.object_path)
        raise ValueError(f"unsupported image_uri kind: {parsed.kind}")

    def read_image(self, image_uri: str) -> Image.Image:
        """根据 image_uri 读取图片并解码为 Pillow Image。"""
        data = self.read_image_bytes(image_uri)
        with Image.open(BytesIO(data)) as image:
            image.load()
            loaded = image.copy()
            loaded.format = image.format
            return loaded

    def read_image_bytes_batch(self, image_uris: Iterable[str]) -> list[DatasetImageBytesReadResult]:
        """批量读取图片 bytes，逐项返回成功值或错误信息。"""
        results: list[DatasetImageBytesReadResult] = []
        for image_uri in image_uris:
            try:
                results.append(DatasetImageBytesReadResult(image_uri=image_uri, ok=True, data=self.read_image_bytes(image_uri)))
            except Exception as exc:
                results.append(DatasetImageBytesReadResult(image_uri=image_uri, ok=False, error=str(exc)))
        return results

    def read_image_batch(self, image_uris: Iterable[str]) -> list[DatasetImageReadResult]:
        """批量读取图片对象，逐项返回成功值或错误信息。"""
        results: list[DatasetImageReadResult] = []
        for image_uri in image_uris:
            try:
                results.append(DatasetImageReadResult(image_uri=image_uri, ok=True, image=self.read_image(image_uri)))
            except Exception as exc:
                results.append(DatasetImageReadResult(image_uri=image_uri, ok=False, error=str(exc)))
        return results

    def iter_images(self, columns: list[str] | None = None) -> Iterator[DatasetImage]:
        """按 Dataset 当前行顺序枚举图片对象。"""
        required_columns = ["image_id", "image_uri"]
        selected_columns = required_columns if columns is None else [*required_columns, *columns]
        frame = self.to_frame(columns=_dedupe_columns(selected_columns))
        for row in frame.to_dict(orient="records"):
            yield DatasetImage(
                image_id=str(row["image_id"]),
                image_uri=str(row["image_uri"]),
                row=row,
                dataset=self,
            )
```

Add helper functions near the bottom:

```python
def _parse_image_uri(image_uri: str) -> ParsedImageUri:
    """解析 Dataset 支持的图片地址类型。"""
    parsed = urlparse(image_uri)
    if parsed.scheme == "s3":
        object_path = parsed.path.lstrip("/")
        if not parsed.netloc or not object_path:
            raise ValueError(f"invalid s3 image_uri: {image_uri}")
        return ParsedImageUri(kind="s3", image_uri=image_uri, bucket=parsed.netloc, object_path=unquote(object_path))
    if parsed.scheme in {"", "file"}:
        return ParsedImageUri(kind="local", image_uri=image_uri, local_path=file_image_uri_to_path(image_uri))
    raise ValueError(f"unsupported image_uri scheme: {parsed.scheme}")


def _dedupe_columns(columns: list[str]) -> list[str]:
    """保持顺序去重，避免用户 columns 重复包含 image_id 或 image_uri。"""
    deduped: list[str] = []
    for column in columns:
        if column not in deduped:
            deduped.append(column)
    return deduped
```

Modify `src/image_gallery/dataset/__init__.py`:

```python
from image_gallery.dataset.dataset import (
    Dataset,
    DatasetImage,
    DatasetImageBytesReadResult,
    DatasetImageReadResult,
)

__all__ = [
    "Dataset",
    "DatasetImage",
    "DatasetImageBytesReadResult",
    "DatasetImageReadResult",
]
```

- [ ] **Step 4: Run Dataset image tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/unit/dataset/test_image_reading.py -q
```

Expected: PASS.

- [ ] **Step 5: Run existing Dataset and storage tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/dataset tests/unit/storage -q
```

Expected: PASS.

- [ ] **Step 6: Commit Dataset image API**

Run:

```bash
git add src/image_gallery/dataset/dataset.py src/image_gallery/dataset/__init__.py tests/unit/dataset/test_image_reading.py
git commit -m "feat: add dataset image reading"
```

## Task 2: Built-in Backend Migration

**Files:**
- Modify: `src/image_gallery/operators/backends/pillow_backend.py`
- Modify: `src/image_gallery/operators/backends/opencv_backend.py`
- Modify: `src/image_gallery/operators/backends/hash_backend.py`
- Modify: `tests/unit/operators/test_pillow_backend.py`
- Modify: `tests/unit/operators/test_opencv_backend.py`
- Modify: `tests/unit/operators/test_hash_backend.py`

- [ ] **Step 1: Add remote Dataset tests for built-in backends**

Add this fake storage helper as a local helper in each of the three backend test files:

```python
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
```

Add to `tests/unit/operators/test_pillow_backend.py`:

```python
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
```

Add to `tests/unit/operators/test_opencv_backend.py`:

```python
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
```

Add to `tests/unit/operators/test_hash_backend.py`:

```python
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
```

- [ ] **Step 2: Run backend tests to verify new remote cases fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_pillow_backend.py tests/unit/operators/test_opencv_backend.py tests/unit/operators/test_hash_backend.py -q
```

Expected: FAIL because the backend implementations still call `file_image_uri_to_path()` and reject `s3://...`.

- [ ] **Step 3: Migrate Pillow backend to DatasetImage**

Modify `src/image_gallery/operators/backends/pillow_backend.py`:

```python
from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset, DatasetImage
from image_gallery.operators.backends.base import BackendAdapter, BackendOperatorRequest, BackendResult
```

Replace `compute_parameters` loop:

```python
        rows: list[dict[str, object]] = []
        for image in dataset.iter_images():
            metadata = read_image_metadata(image)
            rows.append({"image_id": image.image_id, **metadata})
```

Replace `read_image_metadata`:

```python
def read_image_metadata(image: DatasetImage) -> dict[str, object]:
    """读取单张图片的基础元数据。"""
    try:
        loaded = image.read_image()
        return {
            "width": int(loaded.width),
            "height": int(loaded.height),
            "format": str(loaded.format or ""),
            "decode_ok": True,
            "decode_error": "",
        }
    except Exception as exc:
        return {
            "width": pd.NA,
            "height": pd.NA,
            "format": "",
            "decode_ok": False,
            "decode_error": str(exc),
        }
```

Update local test `test_read_image_metadata_returns_basic_fields` to wrap the image in a Dataset:

```python
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
```

- [ ] **Step 4: Migrate OpenCV backend to DatasetImage**

Modify `src/image_gallery/operators/backends/opencv_backend.py` imports:

```python
from pathlib import Path
from typing import Any

import pandas as pd

from image_gallery.dataset import Dataset, DatasetImage
from image_gallery.operators.backends.base import BackendAdapter, BackendOperatorRequest, BackendResult
```

Replace the loop in `compute_parameters`:

```python
        rows: list[dict[str, object]] = []
        for image in dataset.iter_images():
            result: dict[str, object] = {"image_id": image.image_id}
            if "blur_score" in requested_columns:
                result["blur_score"] = compute_blur_score(image)
            if "brightness_score" in requested_columns:
                result["brightness_score"] = compute_brightness_score(image)
            if "contrast_score" in requested_columns:
                result["contrast_score"] = compute_contrast_score(image)
            rows.append(result)
```

Replace the compute helpers:

```python
def compute_blur_score(image: DatasetImage) -> float:
    """计算单张图片的模糊分数，分数越高通常越清晰。"""
    gray = _read_grayscale_values(image)
    try:
        import cv2

        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except ModuleNotFoundError:
        laplacian = _laplacian_values(gray)
        return float(laplacian.var())


def compute_brightness_score(image: DatasetImage) -> float:
    """计算单张图片的平均亮度。"""
    gray = _read_grayscale_values(image)
    return float(gray.mean())


def compute_contrast_score(image: DatasetImage) -> float:
    """计算单张图片的亮度标准差作为对比度。"""
    gray = _read_grayscale_values(image)
    return float(gray.std())


def _read_grayscale_values(image: DatasetImage) -> Any:
    """读取灰度像素数组。"""
    import numpy as np

    loaded = image.read_image()
    return np.asarray(loaded.convert("L"), dtype="float64")
```

Update local test `test_quality_scores_reflect_basic_image_properties` to use DatasetImage objects:

```python
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
```

- [ ] **Step 5: Migrate hash backend to DatasetImage**

Modify `src/image_gallery/operators/backends/hash_backend.py` imports:

```python
import hashlib
from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset, DatasetImage
from image_gallery.operators.backends.base import BackendAdapter, BackendOperatorRequest, BackendResult
```

Replace the loop:

```python
        rows: list[dict[str, object]] = []
        for image in dataset.iter_images():
            rows.append(
                {
                    "image_id": image.image_id,
                    "content_hash": compute_content_hash(image),
                    "phash": compute_phash(image),
                }
            )
```

Replace hash helpers:

```python
def compute_content_hash(image: DatasetImage) -> str:
    """计算图片文件内容 hash。"""
    return hashlib.sha256(image.read_bytes()).hexdigest()


def compute_phash(image: DatasetImage) -> str:
    """计算轻量感知 hash。"""
    loaded = image.read_image()
    gray = loaded.convert("L").resize((8, 8))
    values = list(gray.tobytes())
    average = sum(values) / len(values)
    bits = "".join("1" if value >= average else "0" for value in values)
    return f"{int(bits, 2):016x}"
```

Update local test `test_hash_functions_are_stable_for_same_file`:

```python
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
```

- [ ] **Step 6: Run backend tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_pillow_backend.py tests/unit/operators/test_opencv_backend.py tests/unit/operators/test_hash_backend.py -q
```

Expected: PASS.

- [ ] **Step 7: Run all operator tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators -q
```

Expected: PASS.

- [ ] **Step 8: Commit backend migration**

Run:

```bash
git add src/image_gallery/operators/backends/pillow_backend.py src/image_gallery/operators/backends/opencv_backend.py src/image_gallery/operators/backends/hash_backend.py tests/unit/operators/test_pillow_backend.py tests/unit/operators/test_opencv_backend.py tests/unit/operators/test_hash_backend.py
git commit -m "refactor: read backend images through dataset"
```

## Task 3: BasicCleaner Remote Dataset Integration

**Files:**
- Create: `tests/integration/cleaning/test_basic_cleaner_remote_dataset.py`

- [ ] **Step 1: Write failing BasicCleaner remote Dataset integration test**

Create `tests/integration/cleaning/test_basic_cleaner_remote_dataset.py`:

```python
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
    ok_uri = storage.write_bytes("images/ok.png", _image_bytes(tmp_path / "ok.png", (20, 20), (100, 120, 140)))
    small_uri = storage.write_bytes("images/small.png", _image_bytes(tmp_path / "small.png", (4, 4), (100, 120, 140)))
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
            {"quality.brightness_check": {}},
            {"duplicate.exact_duplicate_check": {}},
        ]
    )

    cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    parameter_table = pd.read_parquet(next((tmp_path / "cleaning").iterdir()) / "parameter_table.parquet")
    assert {"width", "height", "decode_ok", "brightness_score", "content_hash", "phash"}.issubset(
        parameter_table.columns
    )
    assert cleaner.result("format.decode_check")["decode_action"].tolist() == ["keep", "keep"]
    assert cleaner.result("size.dimension_check")["dimension_action"].tolist() == ["keep", "review"]
```

- [ ] **Step 2: Run integration test**

Run:

```bash
.venv/bin/python -m pytest tests/integration/cleaning/test_basic_cleaner_remote_dataset.py -q
```

Expected: PASS after Tasks 1 and 2 are complete. This confirms `BasicCleaner` already preserves the original `Dataset` object through the backend execution path.

- [ ] **Step 3: Run cleaning integration tests**

Run:

```bash
.venv/bin/python -m pytest tests/integration/cleaning -q
```

Expected: PASS.

- [ ] **Step 4: Commit cleaner integration coverage**

Run:

```bash
git add tests/integration/cleaning/test_basic_cleaner_remote_dataset.py
git commit -m "test: cover cleaner remote dataset images"
```

## Task 4: Notebook Validation Design Sync

**Files:**
- Modify: `docs/superpowers/specs/2026-07-03-operators-notebook-validation-design.md`

- [ ] **Step 1: Update the notebook validation spec to remove stale materialization requirement**

Edit `docs/superpowers/specs/2026-07-03-operators-notebook-validation-design.md`.

Replace the non-goal:

```text
6. 不要求阶段 4 后端直接读取 `s3://` URI；MinIO 图片会先通过 `MinioStorage.read_bytes()` 读取并 materialize 到 notebook 本地 cache，再进入算子处理。
```

with:

```text
6. 不在 Notebook 中手写 MinIO 图片 materialize 逻辑；MinIO raw Dataset 应通过绑定 `MinioStorage` 的 `Dataset` 进入算子处理。
```

Replace the section titled `### 3. 读取并 materialize MinIO raw Dataset` with:

````markdown
### 3. 读取 MinIO raw Dataset

使用 `Dataset.from_path(..., storage=minio_storage)` 加载 MinIO raw Dataset，并断言至少包含：

```text
image_id
image_uri
```

MinIO 连接参数从仓库根目录 `.env` 读取，沿用已有 MinIO notebook 的环境变量：

```text
IMAGE_GALLERY_MINIO_ENDPOINT
IMAGE_GALLERY_MINIO_ACCESS_KEY
IMAGE_GALLERY_MINIO_SECRET_KEY
IMAGE_GALLERY_MINIO_BUCKET
```

Notebook 使用 `MinioStorage` 连接 MinIO，然后把连接后的 storage 绑定给 Dataset：

```python
minio_storage = MinioStorage(storage_name="operator_validation_minio").connect(...)
minio_dataset = Dataset.from_path(str(MINIO_RAW_DATASET_PATH), storage=minio_storage)
```

这一段同时验收：

1. MinIO raw Dataset 中的 `s3://...` URI 可被 Dataset 解析。
2. MinIO 对象可通过 Dataset 图片读取 API 读取。
3. MinIO 图片内容可以直接进入阶段 4 算子处理链路。
````

Replace references to `MinIO materialized Dataset` with `MinIO Dataset`.

- [ ] **Step 2: Search for stale materialization wording**

Run:

```bash
rg -n "materialize|materialized|minio_cache|MINIO_CACHE_DIR|本地 cache" docs/superpowers/specs/2026-07-03-operators-notebook-validation-design.md
```

Expected: no stale requirement that MinIO images must be cached locally before operators run. It is acceptable if the text mentions materialization only to say Notebook should not do it.

- [ ] **Step 3: Commit spec sync**

Run:

```bash
git add docs/superpowers/specs/2026-07-03-operators-notebook-validation-design.md
git commit -m "docs: align operator notebook with dataset image reading"
```

## Task 5: Full Verification

**Files:**
- Verify only; no expected source edits.

- [ ] **Step 1: Run focused unit tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/dataset tests/unit/operators tests/unit/cleaning -q
```

Expected: PASS.

- [ ] **Step 2: Run focused integration tests**

Run:

```bash
.venv/bin/python -m pytest tests/integration/cleaning -q
```

Expected: PASS.

- [ ] **Step 3: Run lint on touched source and tests**

Run:

```bash
.venv/bin/python -m ruff check src/image_gallery/dataset src/image_gallery/operators tests/unit/dataset tests/unit/operators tests/integration/cleaning
```

Expected: PASS.

- [ ] **Step 4: Run type check on package**

Run:

```bash
.venv/bin/python -m mypy src/image_gallery
```

Expected: PASS.

- [ ] **Step 5: Inspect final git status**

Run:

```bash
git status --short
```

Expected: only unrelated pre-existing user changes remain. The implementation commits from this plan should be present as separate commits.
