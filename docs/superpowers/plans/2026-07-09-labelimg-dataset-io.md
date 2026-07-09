# LabelImg Dataset I/O Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pluggable `Dataset.load/export` I/O model and the first LabelImg Pascal VOC directory round trip.

**Architecture:** `Dataset` owns the user-facing `load` and `export` entrypoints, while `dataset/io.py` defines loader/exporter protocols and result types. Tabular I/O stays in `dataset/exporters.py`; LabelImg-specific directory layout, XML serialization, XML parsing, and bbox coordinate conversion live in `annotations/labelimg.py`.

**Tech Stack:** Python 3.10, pandas, pyarrow, Pillow, stdlib `xml.etree.ElementTree`, pytest, existing `Dataset.read_image_bytes()`.

## Global Constraints

- First version supports LabelImg Pascal VOC XML only; do not add YOLO TXT, CreateML JSON, COCO, or Label Studio support.
- `Dataset.from_path(...)` must be removed and replaced by `Dataset.load(...)`.
- `Dataset.export(...)` must accept a `DatasetExporter`; do not keep the old `Dataset.export(output_dataset_path, address_policy="keep")` signature.
- `Dataset.write(...)` remains available for writing an in-memory `DataFrame` to a dataset file.
- Dataset annotations stay one image per row in an `annotations` column.
- Bboxes stored in Dataset use relative `relative_xyxy` coordinates in `[0, 1]`.
- LabelImg output layout is `raw.parquet`, `images/<image_id>.<ext>`, and `annotations/<image_id>.xml`.
- LabelImg image basename and XML basename must match.
- Keep implementation local-first; do not launch LabelImg GUI or add service APIs.
- Use `.venv/bin/python -m pytest ...` for verification.

---

## File Structure

- Create `src/image_gallery/dataset/io.py`: defines `DatasetLoader`, `DatasetExporter`, and `DatasetExportResult`.
- Create `src/image_gallery/dataset/exporters.py`: defines `TabularDatasetExporter` and shared table export behavior.
- Modify `src/image_gallery/dataset/dataset.py`: add `Dataset.load(...)`, replace `Dataset.export(...)` with exporter dispatch, and remove `from_path`.
- Modify `src/image_gallery/dataset/__init__.py`: export the new loader/exporter protocols and tabular exporter.
- Create `src/image_gallery/annotations/__init__.py`: exports LabelImg public classes.
- Create `src/image_gallery/annotations/labelimg.py`: LabelImg loader/exporter plus Pascal VOC XML helpers.
- Create `tests/unit/dataset/test_dataset_load_export.py`: core load/export tests.
- Replace `tests/unit/dataset/test_dataset_export.py` or remove it after equivalent tests live in `test_dataset_load_export.py`.
- Create `tests/unit/annotations/test_labelimg.py`: XML conversion, exporter, and loader tests.
- Modify existing tests/examples/helpers/notebooks that call `Dataset.from_path(...)`.
- Do not modify archived docs unless a test imports or executes them.

---

### Task 1: Dataset Load/Export Core

**Files:**
- Create: `src/image_gallery/dataset/io.py`
- Create: `src/image_gallery/dataset/exporters.py`
- Modify: `src/image_gallery/dataset/dataset.py`
- Modify: `src/image_gallery/dataset/__init__.py`
- Test: `tests/unit/dataset/test_dataset_load_export.py`
- Delete after replacement: `tests/unit/dataset/test_dataset_export.py`

**Interfaces:**
- Consumes: existing `Dataset.write(data: pd.DataFrame, output_path: str, storage: Storage | None = None) -> Dataset`.
- Produces: `Dataset.load(source: str | Path | DatasetLoader, storage: Storage | None = None) -> Dataset`.
- Produces: `Dataset.export(exporter: DatasetExporter) -> DatasetExportResult | Dataset`.
- Produces: `TabularDatasetExporter(output_path: str | Path, drop_source_uri: bool = True)`.
- Produces: `DatasetExportResult(output_dir: str | None = None, output_path: str | None = None, image_count: int = 0, annotation_count: int = 0, failures: list[dict[str, object]] = ...)`.

- [ ] **Step 1: Write failing core load/export tests**

Replace `tests/unit/dataset/test_dataset_export.py` with `tests/unit/dataset/test_dataset_load_export.py`:

```python
from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset, DatasetExportResult, DatasetLoader, TabularDatasetExporter


class DemoLoader:
    """测试用 loader，验证 Dataset.load 可以委托外部资源加载。"""

    def __init__(self, dataset_path: str) -> None:
        self.dataset_path = dataset_path

    def load(self) -> Dataset:
        return Dataset.write(
            pd.DataFrame([{"image_id": "img-loader", "image_uri": "/tmp/loader.jpg"}]),
            self.dataset_path,
        )


def test_dataset_load_reads_existing_parquet(tmp_path: Path) -> None:
    output_path = str(tmp_path / "raw.parquet")
    pd.DataFrame([{"image_id": "img-1", "image_uri": "/tmp/a.jpg"}]).to_parquet(output_path, index=False)

    dataset = Dataset.load(output_path)

    assert dataset.dataset_path == output_path
    assert dataset.count() == 1


def test_dataset_load_delegates_loader(tmp_path: Path) -> None:
    loader: DatasetLoader = DemoLoader(str(tmp_path / "loaded.parquet"))

    dataset = Dataset.load(loader)

    assert dataset.to_frame().to_dict("records") == [{"image_id": "img-loader", "image_uri": "/tmp/loader.jpg"}]


def test_dataset_export_uses_tabular_exporter_and_drops_source_uri(tmp_path: Path) -> None:
    input_path = str(tmp_path / "raw.parquet")
    output_path = tmp_path / "export.csv"
    Dataset.write(
        pd.DataFrame(
            [
                {
                    "image_id": "img-1",
                    "image_uri": "/managed/a.jpg",
                    "source_uri": "/external/a.jpg",
                    "width": 10,
                }
            ]
        ),
        input_path,
    )

    result = Dataset.load(input_path).export(TabularDatasetExporter(output_path))

    assert isinstance(result, DatasetExportResult)
    assert result.output_path == str(output_path)
    exported = Dataset.load(str(output_path))
    assert exported.to_frame().to_dict("records") == [
        {"image_id": "img-1", "image_uri": "/managed/a.jpg", "width": 10}
    ]
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/dataset/test_dataset_load_export.py -q
```

Expected: FAIL because `Dataset.load`, `DatasetLoader`, `DatasetExportResult`, and `TabularDatasetExporter` are not defined.

- [ ] **Step 3: Implement protocols and tabular exporter**

Create `src/image_gallery/dataset/io.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from image_gallery.dataset.dataset import Dataset


@dataclass(frozen=True)
class DatasetExportResult:
    """Dataset 导出结果摘要，供目录型和文件型 exporter 共用。"""

    output_dir: str | None = None
    output_path: str | None = None
    image_count: int = 0
    annotation_count: int = 0
    failures: list[dict[str, object]] = field(default_factory=list)


@runtime_checkable
class DatasetLoader(Protocol):
    """把外部资源加载为 Dataset 的协议。"""

    def load(self) -> Dataset:
        """加载外部资源并返回 Dataset。"""
        ...


@runtime_checkable
class DatasetExporter(Protocol):
    """把 Dataset 导出到外部资源的协议。"""

    def export(self, dataset: Dataset) -> DatasetExportResult:
        """导出 Dataset 并返回结果摘要。"""
        ...
```

Create `src/image_gallery/dataset/exporters.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from image_gallery.dataset.io import DatasetExportResult


@dataclass(frozen=True)
class TabularDatasetExporter:
    """把 Dataset 表格导出为 Parquet、CSV 或 JSONL。"""

    output_path: str | Path
    drop_source_uri: bool = True

    def export(self, dataset: object) -> DatasetExportResult:
        """导出 Dataset 表格，默认移除 source_uri 追溯字段。"""
        from image_gallery.dataset.dataset import Dataset

        if not isinstance(dataset, Dataset):
            raise TypeError("dataset must be a Dataset")

        frame = dataset.to_frame()
        if self.drop_source_uri and "source_uri" in frame.columns:
            frame = frame.drop(columns=["source_uri"])

        output_path = str(self.output_path)
        Dataset.write(frame, output_path, storage=dataset.storage)
        return DatasetExportResult(output_path=output_path)
```

- [ ] **Step 4: Modify Dataset load/export**

In `src/image_gallery/dataset/dataset.py`, add imports:

```python
from image_gallery.dataset.io import DatasetExporter, DatasetExportResult, DatasetLoader
```

Replace `from_path` with `load`:

```python
    @classmethod
    def load(cls, source: str | Path | DatasetLoader, storage: Storage | None = None) -> "Dataset":
        """从表格文件或 DatasetLoader 加载 Dataset。"""
        if isinstance(source, DatasetLoader):
            return source.load()
        return cls(dataset_path=str(source), format=_format_from_path(str(source)), storage=storage)
```

Replace the old `export` method with:

```python
    def export(self, exporter: DatasetExporter) -> DatasetExportResult:
        """使用指定 exporter 导出 Dataset。"""
        if not isinstance(exporter, DatasetExporter):
            raise TypeError("exporter must implement DatasetExporter")
        return exporter.export(self)
```

Do not keep `Dataset.from_path(...)`.

- [ ] **Step 5: Update dataset package exports**

Modify `src/image_gallery/dataset/__init__.py`:

```python
from image_gallery.dataset.dataset import (
    Dataset,
    DatasetImage,
    DatasetImageBytesReadResult,
    DatasetImageReadResult,
)
from image_gallery.dataset.exporters import TabularDatasetExporter
from image_gallery.dataset.io import DatasetExporter, DatasetExportResult, DatasetLoader

__all__ = [
    "Dataset",
    "DatasetExporter",
    "DatasetExportResult",
    "DatasetImage",
    "DatasetImageBytesReadResult",
    "DatasetImageReadResult",
    "DatasetLoader",
    "TabularDatasetExporter",
]
```

- [ ] **Step 6: Run core tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/dataset/test_dataset_load_export.py tests/unit/dataset/test_dataset_io.py -q
```

Expected: PASS for the new core tests; older tests may still fail elsewhere due to remaining `Dataset.from_path(...)` references.

- [ ] **Step 7: Commit**

```bash
git add src/image_gallery/dataset tests/unit/dataset/test_dataset_load_export.py tests/unit/dataset/test_dataset_export.py
git commit -m "feat: add pluggable dataset load export"
```

---

### Task 2: LabelImg XML Helpers

**Files:**
- Create: `src/image_gallery/annotations/__init__.py`
- Create: `src/image_gallery/annotations/labelimg.py`
- Test: `tests/unit/annotations/test_labelimg.py`

**Interfaces:**
- Consumes: `DatasetExportResult` from Task 1.
- Produces: `relative_bbox_to_voc_bbox(annotation: dict[str, object], width: int, height: int) -> tuple[int, int, int, int]`.
- Produces: `voc_bbox_to_annotation(label: str, xmin: int, ymin: int, xmax: int, ymax: int, width: int, height: int, difficult: int = 0, truncated: int = 0, pose: str = "Unspecified") -> dict[str, object]`.
- Produces: `write_pascal_voc_xml(...) -> None`.
- Produces: `read_pascal_voc_xml(xml_path: str | Path) -> PascalVocAnnotation`.

- [ ] **Step 1: Write failing XML helper tests**

Create `tests/unit/annotations/test_labelimg.py` with the helper tests first:

```python
from pathlib import Path

import pytest

from image_gallery.annotations.labelimg import (
    read_pascal_voc_xml,
    relative_bbox_to_voc_bbox,
    voc_bbox_to_annotation,
    write_pascal_voc_xml,
)


def test_relative_bbox_to_voc_bbox_uses_image_dimensions() -> None:
    annotation = {
        "label": "person",
        "bbox": {"x_min": 0.1, "y_min": 0.25, "x_max": 0.6, "y_max": 0.75},
        "format": "relative_xyxy",
    }

    assert relative_bbox_to_voc_bbox(annotation, width=100, height=80) == (10, 20, 60, 60)


def test_voc_bbox_to_annotation_stores_relative_coordinates() -> None:
    annotation = voc_bbox_to_annotation(
        label="person",
        xmin=10,
        ymin=20,
        xmax=60,
        ymax=60,
        width=100,
        height=80,
        difficult=1,
        truncated=0,
        pose="Frontal",
    )

    assert annotation == {
        "label": "person",
        "bbox": {"x_min": 0.1, "y_min": 0.25, "x_max": 0.6, "y_max": 0.75},
        "format": "relative_xyxy",
        "source": "labelimg_pascal_voc",
        "difficult": 1,
        "truncated": 0,
        "pose": "Frontal",
    }


def test_pascal_voc_xml_round_trips_objects(tmp_path: Path) -> None:
    xml_path = tmp_path / "img-1.xml"
    image_path = tmp_path / "images" / "img-1.png"
    image_path.parent.mkdir()

    write_pascal_voc_xml(
        xml_path=xml_path,
        folder="images",
        filename="img-1.png",
        image_path=image_path,
        width=100,
        height=80,
        depth=3,
        annotations=[
            {
                "label": "person",
                "bbox": {"x_min": 0.1, "y_min": 0.25, "x_max": 0.6, "y_max": 0.75},
                "format": "relative_xyxy",
                "difficult": 1,
            }
        ],
    )

    parsed = read_pascal_voc_xml(xml_path)

    assert parsed.filename == "img-1.png"
    assert parsed.width == 100
    assert parsed.height == 80
    assert parsed.annotations == [
        {
            "label": "person",
            "bbox": {"x_min": 0.1, "y_min": 0.25, "x_max": 0.6, "y_max": 0.75},
            "format": "relative_xyxy",
            "source": "labelimg_pascal_voc",
            "difficult": 1,
            "truncated": 0,
            "pose": "Unspecified",
        }
    ]


def test_invalid_relative_bbox_is_rejected() -> None:
    annotation = {
        "label": "person",
        "bbox": {"x_min": 0.8, "y_min": 0.1, "x_max": 0.2, "y_max": 0.3},
        "format": "relative_xyxy",
    }

    with pytest.raises(ValueError, match="invalid bbox"):
        relative_bbox_to_voc_bbox(annotation, width=100, height=80)
```

- [ ] **Step 2: Run failing XML helper tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/annotations/test_labelimg.py -q
```

Expected: FAIL because `image_gallery.annotations.labelimg` does not exist.

- [ ] **Step 3: Implement XML dataclass and coordinate helpers**

Create `src/image_gallery/annotations/__init__.py`:

```python
from image_gallery.annotations.labelimg import LabelImgExporter, LabelImgLoader

__all__ = ["LabelImgExporter", "LabelImgLoader"]
```

Start `src/image_gallery/annotations/labelimg.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


@dataclass(frozen=True)
class PascalVocAnnotation:
    """Pascal VOC XML 解析结果。"""

    filename: str
    width: int
    height: int
    depth: int
    annotations: list[dict[str, object]]


def relative_bbox_to_voc_bbox(annotation: dict[str, object], width: int, height: int) -> tuple[int, int, int, int]:
    """把 Dataset 相对 bbox 转换成 Pascal VOC 整数像素 bbox。"""
    bbox = annotation.get("bbox")
    if not isinstance(bbox, dict):
        raise ValueError(f"invalid bbox: {bbox}")
    if annotation.get("format", "relative_xyxy") != "relative_xyxy":
        raise ValueError(f"unsupported annotation format: {annotation.get('format')}")

    x_min = _require_ratio(bbox.get("x_min"), "x_min")
    y_min = _require_ratio(bbox.get("y_min"), "y_min")
    x_max = _require_ratio(bbox.get("x_max"), "x_max")
    y_max = _require_ratio(bbox.get("y_max"), "y_max")
    if x_min >= x_max or y_min >= y_max:
        raise ValueError(f"invalid bbox: {bbox}")
    if width <= 0 or height <= 0:
        raise ValueError(f"width and height must be positive: {width}, {height}")

    return (
        max(1, int(round(x_min * width))),
        max(1, int(round(y_min * height))),
        min(width, int(round(x_max * width))),
        min(height, int(round(y_max * height))),
    )


def voc_bbox_to_annotation(
    *,
    label: str,
    xmin: int,
    ymin: int,
    xmax: int,
    ymax: int,
    width: int,
    height: int,
    difficult: int = 0,
    truncated: int = 0,
    pose: str = "Unspecified",
) -> dict[str, object]:
    """把 Pascal VOC 绝对像素 bbox 转换成 Dataset 相对坐标标注。"""
    if width <= 0 or height <= 0:
        raise ValueError(f"width and height must be positive: {width}, {height}")
    if xmin < 0 or ymin < 0 or xmax <= xmin or ymax <= ymin or xmax > width or ymax > height:
        raise ValueError(f"invalid bbox: {(xmin, ymin, xmax, ymax)}")
    return {
        "label": label,
        "bbox": {
            "x_min": xmin / width,
            "y_min": ymin / height,
            "x_max": xmax / width,
            "y_max": ymax / height,
        },
        "format": "relative_xyxy",
        "source": "labelimg_pascal_voc",
        "difficult": int(difficult),
        "truncated": int(truncated),
        "pose": pose,
    }


def _require_ratio(value: object, name: str) -> float:
    """读取并校验相对坐标。"""
    if not isinstance(value, int | float):
        raise ValueError(f"invalid bbox coordinate {name}: {value}")
    ratio = float(value)
    if ratio < 0.0 or ratio > 1.0:
        raise ValueError(f"invalid bbox coordinate {name}: {value}")
    return ratio
```

- [ ] **Step 4: Implement XML write/read helpers**

Append to `src/image_gallery/annotations/labelimg.py`:

```python
def write_pascal_voc_xml(
    *,
    xml_path: str | Path,
    folder: str,
    filename: str,
    image_path: str | Path,
    width: int,
    height: int,
    depth: int,
    annotations: list[dict[str, object]],
) -> None:
    """写出 LabelImg 可读取的 Pascal VOC XML。"""
    root = ElementTree.Element("annotation")
    ElementTree.SubElement(root, "folder").text = folder
    ElementTree.SubElement(root, "filename").text = filename
    ElementTree.SubElement(root, "path").text = str(Path(image_path).resolve())
    source = ElementTree.SubElement(root, "source")
    ElementTree.SubElement(source, "database").text = "Unknown"
    size = ElementTree.SubElement(root, "size")
    ElementTree.SubElement(size, "width").text = str(width)
    ElementTree.SubElement(size, "height").text = str(height)
    ElementTree.SubElement(size, "depth").text = str(depth)
    ElementTree.SubElement(root, "segmented").text = "0"

    for annotation in annotations:
        xmin, ymin, xmax, ymax = relative_bbox_to_voc_bbox(annotation, width=width, height=height)
        obj = ElementTree.SubElement(root, "object")
        ElementTree.SubElement(obj, "name").text = str(annotation["label"])
        ElementTree.SubElement(obj, "pose").text = str(annotation.get("pose", "Unspecified"))
        ElementTree.SubElement(obj, "truncated").text = str(int(annotation.get("truncated", 0)))
        ElementTree.SubElement(obj, "difficult").text = str(int(annotation.get("difficult", 0)))
        box = ElementTree.SubElement(obj, "bndbox")
        ElementTree.SubElement(box, "xmin").text = str(xmin)
        ElementTree.SubElement(box, "ymin").text = str(ymin)
        ElementTree.SubElement(box, "xmax").text = str(xmax)
        ElementTree.SubElement(box, "ymax").text = str(ymax)

    target = Path(xml_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    ElementTree.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)


def read_pascal_voc_xml(xml_path: str | Path) -> PascalVocAnnotation:
    """读取 Pascal VOC XML 并返回相对坐标标注。"""
    root = ElementTree.parse(xml_path).getroot()
    filename = _required_text(root, "filename")
    size = root.find("size")
    if size is None:
        raise ValueError(f"missing size in annotation xml: {xml_path}")
    width = int(_required_text(size, "width"))
    height = int(_required_text(size, "height"))
    depth = int(size.findtext("depth", default="3"))

    annotations: list[dict[str, object]] = []
    for obj in root.findall("object"):
        label = _required_text(obj, "name")
        box = obj.find("bndbox")
        if box is None:
            raise ValueError(f"missing bndbox in annotation xml: {xml_path}")
        annotations.append(
            voc_bbox_to_annotation(
                label=label,
                xmin=int(_required_text(box, "xmin")),
                ymin=int(_required_text(box, "ymin")),
                xmax=int(_required_text(box, "xmax")),
                ymax=int(_required_text(box, "ymax")),
                width=width,
                height=height,
                difficult=int(obj.findtext("difficult", default="0")),
                truncated=int(obj.findtext("truncated", default="0")),
                pose=obj.findtext("pose", default="Unspecified"),
            )
        )
    return PascalVocAnnotation(filename=filename, width=width, height=height, depth=depth, annotations=annotations)


def _required_text(element: ElementTree.Element, name: str) -> str:
    """读取 XML 必填文本。"""
    value = element.findtext(name)
    if value is None or value == "":
        raise ValueError(f"missing xml field: {name}")
    return value
```

- [ ] **Step 5: Run XML helper tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/annotations/test_labelimg.py -q
```

Expected: PASS for helper tests. Later LabelImg exporter/loader tests are not written yet.

- [ ] **Step 6: Commit**

```bash
git add src/image_gallery/annotations tests/unit/annotations/test_labelimg.py
git commit -m "feat: add labelimg pascal voc helpers"
```

---

### Task 3: LabelImgExporter

**Files:**
- Modify: `src/image_gallery/annotations/labelimg.py`
- Test: `tests/unit/annotations/test_labelimg.py`

**Interfaces:**
- Consumes: `Dataset.read_image_bytes(image_uri: str) -> bytes`.
- Consumes: `Dataset.write(data: pd.DataFrame, output_path: str, storage: Storage | None = None) -> Dataset`.
- Consumes: `write_pascal_voc_xml(...) -> None`.
- Produces: `LabelImgExporter(output_dir: str | Path, annotation_column: str = "annotations", dataset_filename: str = "raw.parquet", overwrite: bool = False)`.

- [ ] **Step 1: Add failing exporter tests**

Append to `tests/unit/annotations/test_labelimg.py`:

```python
import pandas as pd
from PIL import Image

from image_gallery.annotations import LabelImgExporter
from image_gallery.dataset import Dataset


def _write_image(path: Path, size: tuple[int, int] = (10, 8), color: tuple[int, int, int] = (10, 20, 30)) -> bytes:
    Image.new("RGB", size, color=color).save(path)
    return path.read_bytes()


def test_labelimg_exporter_writes_images_dataset_and_existing_xml(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    image_bytes = _write_image(image_path, size=(100, 80))
    dataset = Dataset.write(
        pd.DataFrame(
            [
                {
                    "image_id": "img-1",
                    "image_uri": str(image_path),
                    "width": 100,
                    "height": 80,
                    "file_extension": ".png",
                    "source_uri": "/camera/source.png",
                    "annotations": [
                        {
                            "label": "person",
                            "bbox": {"x_min": 0.1, "y_min": 0.25, "x_max": 0.6, "y_max": 0.75},
                            "format": "relative_xyxy",
                        }
                    ],
                }
            ]
        ),
        str(tmp_path / "raw.parquet"),
    )
    output_dir = tmp_path / "labelimg"

    result = dataset.export(LabelImgExporter(output_dir))

    assert result.output_dir == str(output_dir)
    assert result.image_count == 1
    assert result.annotation_count == 1
    assert (output_dir / "raw.parquet").exists()
    assert (output_dir / "images" / "img-1.png").read_bytes() == image_bytes
    parsed = read_pascal_voc_xml(output_dir / "annotations" / "img-1.xml")
    assert parsed.filename == "img-1.png"
    assert parsed.annotations[0]["label"] == "person"


def test_labelimg_exporter_rejects_existing_output_without_overwrite(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    _write_image(image_path)
    dataset = Dataset.write(
        pd.DataFrame([{"image_id": "img-1", "image_uri": str(image_path), "width": 10, "height": 8}]),
        str(tmp_path / "raw.parquet"),
    )
    output_dir = tmp_path / "labelimg"
    output_dir.mkdir()

    with pytest.raises(FileExistsError):
        dataset.export(LabelImgExporter(output_dir))
```

- [ ] **Step 2: Run failing exporter tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/annotations/test_labelimg.py::test_labelimg_exporter_writes_images_dataset_and_existing_xml tests/unit/annotations/test_labelimg.py::test_labelimg_exporter_rejects_existing_output_without_overwrite -q
```

Expected: FAIL because `LabelImgExporter` is not implemented.

- [ ] **Step 3: Organize LabelImg imports**

Update the top of `src/image_gallery/annotations/labelimg.py` so imports are grouped before any code:

```python
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import json
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd
from PIL import Image

from image_gallery.dataset.io import DatasetExportResult
```

- [ ] **Step 4: Implement LabelImgExporter**

Append the class below the XML helper functions in `src/image_gallery/annotations/labelimg.py`:

```python


@dataclass(frozen=True)
class LabelImgExporter:
    """把 Dataset 导出为 LabelImg Pascal VOC 标注目录。"""

    output_dir: str | Path
    annotation_column: str = "annotations"
    dataset_filename: str = "raw.parquet"
    overwrite: bool = False

    def export(self, dataset: object) -> DatasetExportResult:
        """导出本地图片、原始 Dataset 和可选 Pascal VOC XML。"""
        from image_gallery.dataset.dataset import Dataset

        if not isinstance(dataset, Dataset):
            raise TypeError("dataset must be a Dataset")

        frame = dataset.to_frame()
        _require_columns(frame, ["image_id", "image_uri", "width", "height"])
        output_dir = Path(self.output_dir)
        if output_dir.exists() and not self.overwrite:
            raise FileExistsError(output_dir)
        images_dir = output_dir / "images"
        annotations_dir = output_dir / "annotations"
        images_dir.mkdir(parents=True, exist_ok=True)
        annotations_dir.mkdir(parents=True, exist_ok=True)

        Dataset.write(frame, str(output_dir / self.dataset_filename), storage=dataset.storage)

        image_count = 0
        annotation_count = 0
        for row in frame.to_dict("records"):
            image_id = _require_non_empty(row["image_id"], "image_id")
            image_uri = _require_non_empty(row["image_uri"], "image_uri")
            width = _require_positive_int(row["width"], "width")
            height = _require_positive_int(row["height"], "height")
            image_bytes = dataset.read_image_bytes(image_uri)
            extension = _image_extension(row, image_bytes)
            image_path = images_dir / f"{image_id}{extension}"
            image_path.write_bytes(image_bytes)
            image_count += 1

            annotations = _annotation_list(row.get(self.annotation_column))
            if annotations:
                depth = _image_depth(image_bytes)
                write_pascal_voc_xml(
                    xml_path=annotations_dir / f"{image_id}.xml",
                    folder="images",
                    filename=image_path.name,
                    image_path=image_path,
                    width=width,
                    height=height,
                    depth=depth,
                    annotations=annotations,
                )
                annotation_count += 1

        return DatasetExportResult(output_dir=str(output_dir), image_count=image_count, annotation_count=annotation_count)
```

- [ ] **Step 5: Implement exporter private helpers**

Append to `src/image_gallery/annotations/labelimg.py`:

```python
def _require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    """校验 DataFrame 必填列。"""
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")


def _require_non_empty(value: object, name: str) -> str:
    """读取非空字符串字段。"""
    if value is None or str(value) == "":
        raise ValueError(f"{name} must not be empty")
    return str(value)


def _require_positive_int(value: object, name: str) -> int:
    """读取正整数尺寸字段。"""
    number = int(value)
    if number <= 0:
        raise ValueError(f"{name} must be positive: {value}")
    return number


def _annotation_list(value: object) -> list[dict[str, object]]:
    """把 Dataset 单元格转换为标注列表。"""
    if value is None:
        return []
    if isinstance(value, float) and pd.isna(value):
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise ValueError(f"annotations must be a list: {value}")


def _image_extension(row: dict[str, object], image_bytes: bytes) -> str:
    """确定 LabelImg 本地图片扩展名。"""
    for key in ["file_extension", "source_file_name", "image_uri"]:
        value = row.get(key)
        if value is not None and str(value):
            suffix = Path(str(value)).suffix.lower()
            if suffix:
                return suffix
    with Image.open(BytesIO(image_bytes)) as image:
        if image.format == "JPEG":
            return ".jpg"
    raise ValueError("cannot infer image extension")


def _image_depth(image_bytes: bytes) -> int:
    """读取图片通道数，用于 Pascal VOC size/depth。"""
    with Image.open(BytesIO(image_bytes)) as image:
        if image.mode == "L":
            return 1
        if image.mode in {"RGBA", "CMYK"}:
            return 4
        return 3
```

- [ ] **Step 6: Run exporter tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/annotations/test_labelimg.py -q
```

Expected: PASS for XML helper and exporter tests.

- [ ] **Step 7: Commit**

```bash
git add src/image_gallery/annotations tests/unit/annotations/test_labelimg.py
git commit -m "feat: export datasets for labelimg"
```

---

### Task 4: LabelImgLoader

**Files:**
- Modify: `src/image_gallery/annotations/labelimg.py`
- Test: `tests/unit/annotations/test_labelimg.py`

**Interfaces:**
- Consumes: `Dataset.load(path: str | Path, storage: Storage | None = None) -> Dataset`.
- Consumes: `read_pascal_voc_xml(xml_path: str | Path) -> PascalVocAnnotation`.
- Produces: `LabelImgLoader(input_dir: str | Path, annotation_column: str = "annotations", dataset_filename: str = "raw.parquet", output_filename: str = "labeled.parquet", strict: bool = True)`.

- [ ] **Step 1: Add failing loader tests**

Append to `tests/unit/annotations/test_labelimg.py`:

```python
from image_gallery.annotations import LabelImgLoader


def test_labelimg_loader_writes_labeled_dataset_with_relative_annotations(tmp_path: Path) -> None:
    input_dir = tmp_path / "task"
    annotations_dir = input_dir / "annotations"
    annotations_dir.mkdir(parents=True)
    Dataset.write(
        pd.DataFrame(
            [
                {
                    "image_id": "img-1",
                    "image_uri": str(tmp_path / "img-1.png"),
                    "width": 100,
                    "height": 80,
                }
            ]
        ),
        str(input_dir / "raw.parquet"),
    )
    write_pascal_voc_xml(
        xml_path=annotations_dir / "img-1.xml",
        folder="images",
        filename="img-1.png",
        image_path=input_dir / "images" / "img-1.png",
        width=100,
        height=80,
        depth=3,
        annotations=[
            {
                "label": "person",
                "bbox": {"x_min": 0.1, "y_min": 0.25, "x_max": 0.6, "y_max": 0.75},
                "format": "relative_xyxy",
            }
        ],
    )

    dataset = Dataset.load(LabelImgLoader(input_dir))

    frame = dataset.to_frame()
    assert dataset.dataset_path == str(input_dir / "labeled.parquet")
    assert frame.loc[0, "annotations"] == [
        {
            "label": "person",
            "bbox": {"x_min": 0.1, "y_min": 0.25, "x_max": 0.6, "y_max": 0.75},
            "format": "relative_xyxy",
            "source": "labelimg_pascal_voc",
            "difficult": 0,
            "truncated": 0,
            "pose": "Unspecified",
        }
    ]


def test_labelimg_loader_rejects_unknown_xml_image_id(tmp_path: Path) -> None:
    input_dir = tmp_path / "task"
    annotations_dir = input_dir / "annotations"
    annotations_dir.mkdir(parents=True)
    Dataset.write(
        pd.DataFrame([{"image_id": "img-1", "image_uri": "/tmp/img-1.png", "width": 100, "height": 80}]),
        str(input_dir / "raw.parquet"),
    )
    write_pascal_voc_xml(
        xml_path=annotations_dir / "unknown.xml",
        folder="images",
        filename="unknown.png",
        image_path=input_dir / "images" / "unknown.png",
        width=100,
        height=80,
        depth=3,
        annotations=[],
    )

    with pytest.raises(ValueError, match="no matching image_id"):
        Dataset.load(LabelImgLoader(input_dir))
```

- [ ] **Step 2: Run failing loader tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/annotations/test_labelimg.py::test_labelimg_loader_writes_labeled_dataset_with_relative_annotations tests/unit/annotations/test_labelimg.py::test_labelimg_loader_rejects_unknown_xml_image_id -q
```

Expected: FAIL because `LabelImgLoader` is not implemented.

- [ ] **Step 3: Implement LabelImgLoader**

Append to `src/image_gallery/annotations/labelimg.py`. `json` is already included in the top-level imports from Task 3.

```python
@dataclass(frozen=True)
class LabelImgLoader:
    """从 LabelImg Pascal VOC 标注目录加载带 annotations 的 Dataset。"""

    input_dir: str | Path
    annotation_column: str = "annotations"
    dataset_filename: str = "raw.parquet"
    output_filename: str = "labeled.parquet"
    strict: bool = True

    def load(self) -> object:
        """读取 raw.parquet 和 annotations/*.xml，写出 labeled.parquet。"""
        from image_gallery.dataset.dataset import Dataset

        input_dir = Path(self.input_dir)
        raw_path = input_dir / self.dataset_filename
        dataset = Dataset.load(str(raw_path))
        frame = dataset.to_frame()
        _require_columns(frame, ["image_id", "width", "height"])

        rows_by_id = {str(row["image_id"]): index for index, row in frame.iterrows()}
        annotations_by_id: dict[str, list[dict[str, object]]] = {image_id: [] for image_id in rows_by_id}
        failures: list[dict[str, object]] = []

        for xml_path in sorted((input_dir / "annotations").glob("*.xml")):
            image_id = xml_path.stem
            if image_id not in rows_by_id:
                _record_or_raise(failures, self.strict, f"annotation xml has no matching image_id: {xml_path}")
                continue
            row = frame.loc[rows_by_id[image_id]]
            parsed = read_pascal_voc_xml(xml_path)
            width = _require_positive_int(row["width"], "width")
            height = _require_positive_int(row["height"], "height")
            if parsed.width != width or parsed.height != height:
                _record_or_raise(
                    failures,
                    self.strict,
                    f"annotation size mismatch for image_id={image_id}: dataset=({width},{height}), xml=({parsed.width},{parsed.height})",
                )
                continue
            annotations_by_id[image_id] = parsed.annotations

        frame[self.annotation_column] = [annotations_by_id[str(image_id)] for image_id in frame["image_id"]]
        output_path = input_dir / self.output_filename
        Dataset.write(frame, str(output_path), storage=dataset.storage)
        if failures:
            (input_dir / "labelimg_load_report.json").write_text(
                json.dumps({"failures": failures}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return Dataset.load(str(output_path), storage=dataset.storage)


def _record_or_raise(failures: list[dict[str, object]], strict: bool, message: str) -> None:
    """按 strict 策略记录或抛出 LabelImg 加载错误。"""
    if strict:
        raise ValueError(message)
    failures.append({"error_message": message})
```

- [ ] **Step 4: Run loader tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/annotations/test_labelimg.py -q
```

Expected: PASS for XML helper, exporter, and loader tests.

- [ ] **Step 5: Commit**

```bash
git add src/image_gallery/annotations tests/unit/annotations/test_labelimg.py
git commit -m "feat: load labelimg annotations into dataset"
```

---

### Task 5: Replace Dataset.from_path and Verify Full Suite

**Files:**
- Modify: `src/image_gallery/importers/dataset_file.py`
- Modify: `notebooks/_helpers/datasets.py`
- Modify: `examples/stage2_import_local_directory.py`
- Modify: active notebooks containing `Dataset.from_path(...)`
- Modify: tests under `tests/` containing `Dataset.from_path(...)`
- Modify: any source file containing `Dataset.from_path(...)`

**Interfaces:**
- Consumes: `Dataset.load(...)` from Task 1.
- Consumes: `TabularDatasetExporter` from Task 1.
- Produces: no new API; all active code uses `Dataset.load(...)`.

- [ ] **Step 1: Replace direct `Dataset.from_path(...)` calls**

Use `rg` to locate active references:

```bash
rg -n "Dataset\\.from_path" src tests examples notebooks
```

Apply these replacements in active code:

```python
Dataset.from_path(path)
```

becomes:

```python
Dataset.load(path)
```

and:

```python
Dataset.from_path(path, storage=storage)
```

becomes:

```python
Dataset.load(path, storage=storage)
```

Do not edit archived docs under `docs/superpowers/archive/`.

- [ ] **Step 2: Replace old Dataset tabular export call**

The old Dataset-level export call:

```python
Dataset.load(input_path).export(output_path, address_policy="keep")
```

must become:

```python
Dataset.load(input_path).export(TabularDatasetExporter(output_path))
```

Only change Dataset-level `export`. Do not change `BasicCleaner.export(kind, path)` or `CleanerResult.export(kind, path)` in this task; those are separate cleaning APIs.

- [ ] **Step 3: Update imports where needed**

When a file uses `TabularDatasetExporter`, import it:

```python
from image_gallery.dataset import Dataset, TabularDatasetExporter
```

If the file only changed `from_path` to `load`, keep existing imports.

- [ ] **Step 4: Run reference scan**

Run:

```bash
rg -n "Dataset\\.from_path|Dataset\\.load\\([^\\)]*\\)\\.export\\([^T]" src tests examples notebooks
```

Expected:

- No `Dataset.from_path` matches in `src`, `tests`, `examples`, or active notebooks.
- No old Dataset-level export call remains.
- Matches for `cleaner.export(...)` may remain and are allowed.

- [ ] **Step 5: Run focused unit tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/dataset tests/unit/annotations tests/unit/importers/test_dataset_parser.py tests/unit/importers/test_import_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 6: Run integration tests that exercise Dataset image reads and exports**

Run:

```bash
.venv/bin/python -m pytest tests/integration/cleaning/test_basic_cleaner_remote_dataset.py tests/integration/cleaning/test_basic_cleaner_export.py -q
```

Expected: PASS.

- [ ] **Step 7: Run lint and full tests if focused tests pass**

Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m mypy src/image_gallery
```

Expected: all commands PASS.

- [ ] **Step 8: Commit**

```bash
git add src tests examples notebooks
git commit -m "refactor: migrate dataset io to load export"
```

---

## Self-Review

Spec coverage:

1. `Dataset.load/export` model is covered by Task 1 and migrated in Task 5.
2. Pluggable loader/exporter protocols are covered by Task 1.
3. LabelImg Pascal VOC export is covered by Task 3.
4. LabelImg Pascal VOC load-back is covered by Task 4.
5. Relative bbox storage and Pascal VOC absolute conversion are covered by Task 2.
6. One-row-per-image `annotations` column is covered by Task 4.
7. Split `images/` and `annotations/` directory protocol is covered by Task 3 tests and Task 4 loader.
8. Full API migration away from `Dataset.from_path` is covered by Task 5.

Placeholder scan:

1. The plan does not use `TBD`, `TODO`, `implement later`, or empty edge-case instructions.
2. Every code-changing task includes concrete test code, implementation snippets, commands, and expected results.

Type consistency:

1. `DatasetLoader.load() -> Dataset` is used by `Dataset.load(loader)`.
2. `DatasetExporter.export(dataset) -> DatasetExportResult` is used by `Dataset.export(exporter)`.
3. `TabularDatasetExporter`, `LabelImgExporter`, and `LabelImgLoader` names are consistent across tasks.
4. `annotations` payload shape matches the spec and is used by XML helper, exporter, and loader.
