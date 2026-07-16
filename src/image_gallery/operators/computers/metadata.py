from io import BytesIO

import pandas as pd
from PIL import Image

from image_gallery.operators.computers.base import (
    ExecutionMode,
    ImageBatchItem,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)


class ImageMetadataComputer(ParameterComputer):
    """基于 Cleaner 共享 ImageBatch 生产解码和尺寸参数。"""

    name = "image_metadata_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset(
        {
            "width",
            "height",
            "format",
            "decode_ok",
            "decode_error",
            "file_size",
        }
    )

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """从共享 ImageBatch 中提取被请求的元数据参数。"""
        if request.image_batch is None:
            raise ValueError("ImageMetadataComputer requires image_batch")

        requested = set(request.requested_parameters)
        produced = requested & set(self.produced_parameters)
        rows: list[dict[str, object]] = []
        for item in request.image_batch.items:
            values = self._values_for_item(item)
            row: dict[str, object] = {"image_id": item.image_id}
            for parameter in sorted(produced):
                row[parameter] = values[parameter]
            rows.append(row)

        manifest: dict[str, dict[str, object]] = {
            parameter: {
                "computer": self.name,
                "execution_mode": self.execution_mode.value,
                "config_hash": request.config_hash,
            }
            for parameter in sorted(produced)
        }
        return ParameterResult(
            parameter_updates=pd.DataFrame(rows),
            relation_updates={},
            artifact_refs={},
            parameter_manifest=manifest,
        )

    def _values_for_item(self, item: ImageBatchItem) -> dict[str, object]:
        """把单张共享图片上下文转换为元数据字段。"""
        if item.error or item.image is None:
            return {
                "width": pd.NA,
                "height": pd.NA,
                "format": "",
                "decode_ok": False,
                "decode_error": str(item.error or "image decode failed"),
                "file_size": len(item.data) if item.data is not None else pd.NA,
            }
        return {
            "width": int(item.image.width),
            "height": int(item.image.height),
            "format": str(getattr(item.image, "format", "") or ""),
            "decode_ok": True,
            "decode_error": "",
            "file_size": len(item.data) if item.data is not None else pd.NA,
        }


class ImageFormatDetailComputer(ParameterComputer):
    """生产多帧和 EXIF 方向风险参数。"""

    name = "image_format_detail_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"frame_count", "animated", "exif_orientation", "orientation_risk"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """从共享 ImageBatch 中提取格式细节参数。"""
        if request.image_batch is None:
            raise ValueError("ImageFormatDetailComputer requires image_batch")

        requested = set(request.requested_parameters)
        produced = requested & set(self.produced_parameters)
        rows: list[dict[str, object]] = []
        for item in request.image_batch.items:
            values = self._values_for_item(item)
            row: dict[str, object] = {"image_id": item.image_id}
            for parameter in sorted(produced):
                row[parameter] = values[parameter]
            rows.append(row)

        manifest: dict[str, dict[str, object]] = {
            parameter: {
                "computer": self.name,
                "execution_mode": self.execution_mode.value,
                "config_hash": request.config_hash,
            }
            for parameter in sorted(produced)
        }
        return ParameterResult(
            parameter_updates=pd.DataFrame(rows),
            relation_updates={},
            artifact_refs={},
            parameter_manifest=manifest,
        )

    def _values_for_item(self, item: ImageBatchItem) -> dict[str, object]:
        """把单张图片转换为多帧和方向风险字段。"""
        if item.error or item.image is None:
            return {
                "frame_count": pd.NA,
                "animated": False,
                "exif_orientation": pd.NA,
                "orientation_risk": False,
            }

        frame_count, animated, orientation = _read_format_details(item)
        return {
            "frame_count": frame_count,
            "animated": animated,
            "exif_orientation": orientation if orientation is not None else pd.NA,
            "orientation_risk": orientation not in (None, 1),
        }


def _read_format_details(item: ImageBatchItem) -> tuple[int, bool, int | None]:
    """优先从原始 bytes 读取多帧和 EXIF 元数据，失败时回退到解码图片。"""
    if item.data is not None:
        try:
            with Image.open(BytesIO(item.data)) as image:
                frame_count = int(getattr(image, "n_frames", 1) or 1)
                animated = bool(getattr(image, "is_animated", False) or frame_count > 1)
                return frame_count, animated, _read_exif_orientation(image)
        # Pillow 插件解码失败时回退到已加载的 image 对象。
        except Exception:  # noqa: BLE001
            return _read_format_details_from_image(item.image)
    return _read_format_details_from_image(item.image)


def _read_format_details_from_image(image: object | None) -> tuple[int, bool, int | None]:
    """从已解码图片对象读取格式细节。"""
    if image is None:
        return 1, False, None
    frame_count = int(getattr(image, "n_frames", 1) or 1)
    animated = bool(getattr(image, "is_animated", False) or frame_count > 1)
    return frame_count, animated, _read_exif_orientation(image)


def _read_exif_orientation(image: object) -> int | None:
    """读取 EXIF orientation，读取失败时返回 None。"""
    getexif = getattr(image, "getexif", None)
    if getexif is None:
        return None
    try:
        orientation = getexif().get(274)
    # EXIF 后端异常类型不稳定，方向缺失按 None 处理。
    except Exception:  # noqa: BLE001
        return None
    if orientation is None:
        return None
    try:
        return int(orientation)
    except (TypeError, ValueError):
        return None
