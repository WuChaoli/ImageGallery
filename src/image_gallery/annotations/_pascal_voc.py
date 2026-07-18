from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from defusedxml import ElementTree as SafeElementTree
from defusedxml.common import DefusedXmlException

from image_gallery.annotations._tabular_values import int_value


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
        ElementTree.SubElement(obj, "truncated").text = str(int_value(annotation.get("truncated", 0), "truncated"))
        ElementTree.SubElement(obj, "difficult").text = str(int_value(annotation.get("difficult", 0), "difficult"))
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
