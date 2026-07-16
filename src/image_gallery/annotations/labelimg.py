from __future__ import annotations

import json
import math
from dataclasses import dataclass
from io import BytesIO
from numbers import Real
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree

import pandas as pd
from defusedxml import ElementTree as SafeElementTree
from defusedxml.common import DefusedXmlException
from PIL import Image

from image_gallery.dataset.io import DatasetExportResult


@dataclass(frozen=True)
class PascalVocAnnotation:
    """Pascal VOC XML 解析结果。"""

    filename: str
    width: int
    height: int
    depth: int
    annotations: list[dict[str, object]]


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
        _require_unique_non_empty_image_ids(frame)

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
        for row in cast(list[dict[str, object]], frame.to_dict("records")):
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

        return DatasetExportResult(
            output_dir=str(output_dir),
            image_count=image_count,
            annotation_count=annotation_count,
        )


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

        rows_by_id = {str(row["image_id"]): cast("pd.Series[Any]", row) for _, row in frame.iterrows()}
        annotations_by_id: dict[str, list[dict[str, object]]] = {image_id: [] for image_id in rows_by_id}
        failures: list[dict[str, object]] = []

        for xml_path in sorted((input_dir / "annotations").glob("*.xml")):
            image_id = xml_path.stem
            if image_id not in rows_by_id:
                _record_or_raise(failures, self.strict, f"annotation xml has no matching image_id: {xml_path}")
                continue
            row = rows_by_id[image_id]
            parsed = read_pascal_voc_xml(xml_path)
            width = _require_positive_int(row["width"], "width")
            height = _require_positive_int(row["height"], "height")
            if parsed.width != width or parsed.height != height:
                _record_or_raise(
                    failures,
                    self.strict,
                    (
                        f"annotation size mismatch for image_id={image_id}: "
                        f"dataset=({width},{height}), xml=({parsed.width},{parsed.height})"
                    ),
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


def relative_bbox_to_voc_bbox(annotation: dict[str, object], width: int, height: int) -> tuple[int, int, int, int]:
    """把 Dataset 相对 bbox 转换成 Pascal VOC 整数像素 bbox。"""
    bbox = annotation.get("bbox")
    if not isinstance(bbox, dict):
        raise TypeError(f"invalid bbox: {bbox}")
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
        ElementTree.SubElement(obj, "truncated").text = str(_int_value(annotation.get("truncated", 0), "truncated"))
        ElementTree.SubElement(obj, "difficult").text = str(_int_value(annotation.get("difficult", 0), "difficult"))
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
    try:
        root = SafeElementTree.parse(xml_path).getroot()
    except DefusedXmlException as exc:
        raise ValueError(f"unsafe annotation XML: {xml_path}") from exc
    if root is None:
        raise ValueError(f"annotation XML has no root element: {xml_path}")
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


def _require_ratio(value: object, name: str) -> float:
    """读取并校验相对坐标。"""
    if not isinstance(value, int | float):
        raise TypeError(f"invalid bbox coordinate {name}: {value}")
    ratio = float(value)
    if ratio < 0.0 or ratio > 1.0:
        raise ValueError(f"invalid bbox coordinate {name}: {value}")
    return ratio


def _required_text(element: ElementTree.Element, name: str) -> str:
    """读取 XML 必填文本。"""
    value = element.findtext(name)
    if value is None or value == "":
        raise ValueError(f"missing xml field: {name}")
    return value


def _require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    """校验 DataFrame 必填列。"""
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")


def _require_unique_non_empty_image_ids(frame: pd.DataFrame) -> None:
    """校验 image_id 非空且唯一，避免导出文件互相覆盖。"""
    image_ids = [str(value) for value in frame["image_id"]]
    for image_id in image_ids:
        if image_id == "":
            raise ValueError("image_id must not be empty")
    duplicated = cast(pd.Series, frame["image_id"][frame["image_id"].duplicated()])
    if not duplicated.empty:
        raise ValueError(f"duplicate image_id in dataset export: {duplicated.iloc[0]}")


def _require_non_empty(value: object, name: str) -> str:
    """读取非空字符串字段。"""
    if value is None or str(value) == "":
        raise ValueError(f"{name} must not be empty")
    return str(value)


def _require_positive_int(value: object, name: str) -> int:
    """读取正整数尺寸字段。"""
    number = _int_value(value, name)
    if number <= 0:
        raise ValueError(f"{name} must be positive: {value}")
    return number


def _int_value(value: object, name: str) -> int:
    """把常见表格/XML 数字值转换为 int。"""
    if isinstance(value, str):
        return int(value)
    if isinstance(value, Real):
        return int(float(value))
    raise ValueError(f"{name} must be an integer-compatible value: {value}")


def _annotation_list(value: object) -> list[dict[str, object]]:
    """把 Dataset 单元格转换为标注列表。"""
    if _is_missing(value):
        return []
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        value = cast(list[object], tolist())
    if isinstance(value, list | tuple):
        items = list(value)
        if not all(isinstance(item, dict) for item in items):
            raise ValueError(f"annotations must contain dict items: {value}")
        return cast(list[dict[str, object]], items)
    raise ValueError(f"annotations must be a list: {value}")


def _is_missing(value: object) -> bool:
    """判断 DataFrame 单元格是否为空值。"""
    if value is None:
        return True
    return bool(isinstance(value, float) and math.isnan(value))


def _image_extension(row: dict[str, object], image_bytes: bytes) -> str:
    """确定 LabelImg 本地图片扩展名。"""
    extension = _normalized_extension(row.get("file_extension"))
    if extension:
        return extension
    for key in ["source_file_name", "image_uri"]:
        extension = _normalized_extension(row.get(key))
        if extension:
            return extension
    with Image.open(BytesIO(image_bytes)) as image:
        if image.format == "JPEG":
            return ".jpg"
    raise ValueError("cannot infer image extension")


def _normalized_extension(value: object) -> str | None:
    """从字段值中提取扩展名。"""
    if _is_missing(value) or str(value) == "":
        return None
    text = str(value)
    if text.startswith(".") and "/" not in text and "\\" not in text:
        return text.lower()
    suffix = Path(text).suffix.lower()
    return suffix or None


def _image_depth(image_bytes: bytes) -> int:
    """读取图片通道数，用于 Pascal VOC size/depth。"""
    with Image.open(BytesIO(image_bytes)) as image:
        if image.mode == "L":
            return 1
        if image.mode in {"RGBA", "CMYK"}:
            return 4
        return 3


def _record_or_raise(failures: list[dict[str, object]], strict: bool, message: str) -> None:
    """按 strict 策略记录或抛出 LabelImg 加载错误。"""
    if strict:
        raise ValueError(message)
    failures.append({"error_message": message})
