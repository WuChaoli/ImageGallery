from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pandas as pd

from image_gallery.annotations._pascal_voc import (
    read_pascal_voc_xml as _read_pascal_voc_xml,
)
from image_gallery.annotations._pascal_voc import (
    relative_bbox_to_voc_bbox as _relative_bbox_to_voc_bbox,
)
from image_gallery.annotations._pascal_voc import (
    voc_bbox_to_annotation as _voc_bbox_to_annotation,
)
from image_gallery.annotations._pascal_voc import (
    write_pascal_voc_xml as _write_pascal_voc_xml,
)
from image_gallery.annotations._tabular_values import (
    annotation_list as _annotation_list,
)
from image_gallery.annotations._tabular_values import (
    image_depth as _image_depth,
)
from image_gallery.annotations._tabular_values import (
    image_extension as _image_extension,
)
from image_gallery.annotations._tabular_values import (
    require_columns as _require_columns,
)
from image_gallery.annotations._tabular_values import (
    require_non_empty as _require_non_empty,
)
from image_gallery.annotations._tabular_values import (
    require_positive_int as _require_positive_int,
)
from image_gallery.annotations._tabular_values import (
    require_unique_non_empty_image_ids as _require_unique_non_empty_image_ids,
)
from image_gallery.dataset.io import DatasetExportResult


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
    return _relative_bbox_to_voc_bbox(annotation, width, height)


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
    return _voc_bbox_to_annotation(
        label=label,
        xmin=xmin,
        ymin=ymin,
        xmax=xmax,
        ymax=ymax,
        width=width,
        height=height,
        difficult=difficult,
        truncated=truncated,
        pose=pose,
    )


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
    _write_pascal_voc_xml(
        xml_path=xml_path,
        folder=folder,
        filename=filename,
        image_path=image_path,
        width=width,
        height=height,
        depth=depth,
        annotations=annotations,
    )


def read_pascal_voc_xml(xml_path: str | Path) -> PascalVocAnnotation:
    """读取 Pascal VOC XML 并返回相对坐标标注。"""
    parsed = _read_pascal_voc_xml(xml_path)
    return PascalVocAnnotation(
        filename=parsed.filename,
        width=parsed.width,
        height=parsed.height,
        depth=parsed.depth,
        annotations=parsed.annotations,
    )


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
                write_pascal_voc_xml(
                    xml_path=annotations_dir / f"{image_id}.xml",
                    folder="images",
                    filename=image_path.name,
                    image_path=image_path,
                    width=width,
                    height=height,
                    depth=_image_depth(image_bytes),
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
        dataset = Dataset.load(str(input_dir / self.dataset_filename))
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


def _record_or_raise(failures: list[dict[str, object]], strict: bool, message: str) -> None:
    """按 strict 策略记录或抛出 LabelImg 加载错误。"""
    if strict:
        raise ValueError(message)
    failures.append({"error_message": message})
