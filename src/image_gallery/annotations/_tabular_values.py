import math
from io import BytesIO
from numbers import Real
from pathlib import Path
from typing import Any, cast

import pandas as pd
from PIL import Image


def require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    """校验 DataFrame 必填列。"""
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")


def require_unique_non_empty_image_ids(frame: pd.DataFrame) -> None:
    """校验 image_id 非空且唯一，避免导出文件互相覆盖。"""
    image_ids = [str(value) for value in frame["image_id"]]
    if "" in image_ids:
        raise ValueError("image_id must not be empty")
    duplicated = cast("pd.Series[Any]", frame["image_id"][frame["image_id"].duplicated()])
    if not duplicated.empty:
        raise ValueError(f"duplicate image_id in dataset export: {duplicated.iloc[0]}")


def require_non_empty(value: object, name: str) -> str:
    """读取非空字符串字段。"""
    if value is None or str(value) == "":
        raise ValueError(f"{name} must not be empty")
    return str(value)


def require_positive_int(value: object, name: str) -> int:
    """读取正整数尺寸字段。"""
    number = int_value(value, name)
    if number <= 0:
        raise ValueError(f"{name} must be positive: {value}")
    return number


def int_value(value: object, name: str) -> int:
    """把常见表格/XML 数字值转换为 int。"""
    if isinstance(value, str):
        return int(value)
    if isinstance(value, Real):
        return int(float(value))
    raise ValueError(f"{name} must be an integer-compatible value: {value}")


def annotation_list(value: object) -> list[dict[str, object]]:
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


def image_extension(row: dict[str, object], image_bytes: bytes) -> str:
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


def image_depth(image_bytes: bytes) -> int:
    """读取图片通道数，用于 Pascal VOC size/depth。"""
    with Image.open(BytesIO(image_bytes)) as image:
        if image.mode == "L":
            return 1
        if image.mode in {"RGBA", "CMYK"}:
            return 4
        return 3
