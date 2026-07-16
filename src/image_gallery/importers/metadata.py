import hashlib
import mimetypes
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from PIL import Image

EXIF_ORIENTATION_TAG = 274
EXIF_DATETIME_TAG = 306
EXIF_DATETIME_ORIGINAL_TAG = 36867
EXIF_MAKE_TAG = 271
EXIF_MODEL_TAG = 272
EXIF_GPS_INFO_TAG = 34853
GPS_LATITUDE_REF_TAG = 1
GPS_LATITUDE_TAG = 2
GPS_LONGITUDE_REF_TAG = 3
GPS_LONGITUDE_TAG = 4


def extract_basic_metadata(path: str | Path) -> dict[str, Any]:
    """抽取导入阶段 raw Dataset 需要的低成本基础事实。"""
    image_path = Path(path)
    data = image_path.read_bytes()
    image_content_hash = "sha256:" + hashlib.sha256(data).hexdigest()
    with Image.open(image_path) as image:
        bands = image.getbands()
        width = image.width
        height = image.height
        frame_count = int(getattr(image, "n_frames", 1) or 1)
        exif_metadata = _extract_exif_metadata(image)
        dpi_x, dpi_y = _extract_dpi(image.info.get("dpi"))
        return {
            "file_size_bytes": len(data),
            "image_content_hash": image_content_hash,
            "file_extension": image_path.suffix.lower(),
            "mime_type": _infer_mime_type(image_path, image.format),
            "image_format": image.format or image_path.suffix.lstrip(".").upper(),
            "width": width,
            "height": height,
            "pixel_count": width * height,
            "aspect_ratio": width / height if height else None,
            "orientation": _orientation(width, height),
            "channels": len(bands),
            "color_mode": image.mode,
            "has_alpha": _has_alpha(image),
            "animated": frame_count > 1,
            "frame_count": frame_count,
            "icc_profile_present": bool(image.info.get("icc_profile")),
            "dpi_x": dpi_x,
            "dpi_y": dpi_y,
            **exif_metadata,
        }


def _infer_mime_type(path: Path, image_format: str | None) -> str | None:
    """根据文件后缀和 Pillow format 推断 MIME type。"""
    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type:
        return mime_type
    if image_format:
        return Image.MIME.get(image_format.upper())
    return None


def _orientation(width: int, height: int) -> str:
    """根据宽高判断图片方向。"""
    if width > height:
        return "landscape"
    if width < height:
        return "portrait"
    return "square"


def _has_alpha(image: Image.Image) -> bool:
    """判断图片是否包含 alpha 通道或调色板透明信息。"""
    if "A" in image.getbands():
        return True
    return "transparency" in image.info


def _extract_dpi(dpi: object) -> tuple[float | None, float | None]:
    """从 Pillow info 中抽取 DPI，格式异常时返回空值。"""
    if not isinstance(dpi, tuple) or len(dpi) < 2:
        return None, None
    try:
        return float(dpi[0]), float(dpi[1])
    except (TypeError, ValueError):
        return None, None


def _extract_exif_metadata(image: Image.Image) -> dict[str, object]:
    """读取轻量 EXIF、camera 和 GPS 字段，解析失败不阻断导入。"""
    metadata: dict[str, object] = {
        "exif_orientation": None,
        "exif_datetime": None,
        "camera_make": None,
        "camera_model": None,
        "gps_present": False,
        "gps_latitude": None,
        "gps_longitude": None,
    }
    try:
        exif = image.getexif()
    # Pillow 插件可能抛出格式专用异常，元数据缺失不应中断导入。
    except Exception:  # noqa: BLE001
        return metadata
    if not exif:
        return metadata

    metadata["exif_orientation"] = exif.get(EXIF_ORIENTATION_TAG)
    metadata["exif_datetime"] = exif.get(EXIF_DATETIME_ORIGINAL_TAG) or exif.get(EXIF_DATETIME_TAG)
    metadata["camera_make"] = _clean_optional_text(exif.get(EXIF_MAKE_TAG))
    metadata["camera_model"] = _clean_optional_text(exif.get(EXIF_MODEL_TAG))

    gps_info = _get_gps_info(exif)
    metadata["gps_present"] = bool(gps_info)
    if gps_info:
        metadata["gps_latitude"] = _gps_coordinate(gps_info, GPS_LATITUDE_REF_TAG, GPS_LATITUDE_TAG)
        metadata["gps_longitude"] = _gps_coordinate(gps_info, GPS_LONGITUDE_REF_TAG, GPS_LONGITUDE_TAG)
    return metadata


def _clean_optional_text(value: object) -> str | None:
    """清理 EXIF 文本字段，空字符串视为缺失。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _get_gps_info(exif: Image.Exif) -> dict[int, object]:
    """兼容 Pillow GPS IFD 读取差异。"""
    gps_ifd: object
    try:
        gps_ifd = exif.get_ifd(EXIF_GPS_INFO_TAG)
    # 不同 Pillow/EXIF 后端的异常类型不稳定，失败时回退到基础字段。
    except Exception:  # noqa: BLE001
        gps_ifd = exif.get(EXIF_GPS_INFO_TAG)
    if not isinstance(gps_ifd, dict):
        return {}

    result: dict[int, object] = {}
    for key, value in gps_ifd.items():
        if isinstance(key, int):
            result[key] = value
    return result


def _gps_coordinate(gps_info: dict[int, object], ref_tag: int, value_tag: int) -> float | None:
    """把 EXIF GPS 度分秒转换成十进制度。"""
    ref = gps_info.get(ref_tag)
    value = gps_info.get(value_tag)
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 3:
        return None
    try:
        degrees, minutes, seconds = value
        coordinate = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
    except (TypeError, ValueError):
        return None
    if ref in {"S", "W", b"S", b"W"}:
        coordinate = -coordinate
    return coordinate
