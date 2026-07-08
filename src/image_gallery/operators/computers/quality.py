import numpy as np
import pandas as pd
from numpy.typing import NDArray

from image_gallery.operators.computers.base import (
    ExecutionMode,
    ImageBatchItem,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)


class ImageQualityComputer(ParameterComputer):
    """基于共享解码图片生产基础质量参数。"""

    name = "image_quality_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"blur_score", "brightness_score", "contrast_score", "blank_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """生产本次请求的质量参数。"""
        if request.image_batch is None:
            raise ValueError("ImageQualityComputer requires image_batch")

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
        """把单张图片转换为质量分数。"""
        if item.error or item.image is None:
            return {
                "blur_score": pd.NA,
                "brightness_score": pd.NA,
                "contrast_score": pd.NA,
                "blank_score": pd.NA,
            }

        grayscale = item.image.convert("L")
        array = np.asarray(grayscale, dtype=np.float64)
        brightness = float(array.mean())
        contrast = float(array.std())
        blur = _laplacian_variance(array)
        blank = 1.0 if contrast <= 1.0 else 0.0
        return {
            "blur_score": blur,
            "brightness_score": brightness,
            "contrast_score": contrast,
            "blank_score": blank,
        }


class ImageQualityDetailComputer(ParameterComputer):
    """生产曝光、噪声和低信息量质量参数。"""

    name = "image_quality_detail_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset(
        {
            "dark_pixel_ratio",
            "bright_pixel_ratio",
            "clipped_pixel_ratio",
            "noise_score",
            "mono_color_score",
        }
    )

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """从共享 ImageBatch 中提取第二批轻量质量参数。"""
        if request.image_batch is None:
            raise ValueError("ImageQualityDetailComputer requires image_batch")

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
        """把单张图片转换为曝光、噪声和单色分数。"""
        if item.error or item.image is None:
            return {
                "dark_pixel_ratio": pd.NA,
                "bright_pixel_ratio": pd.NA,
                "clipped_pixel_ratio": pd.NA,
                "noise_score": pd.NA,
                "mono_color_score": pd.NA,
            }

        grayscale = item.image.convert("L")
        gray = np.asarray(grayscale, dtype=np.float64)
        rgb = np.asarray(item.image.convert("RGB"), dtype=np.float64)
        return {
            "dark_pixel_ratio": _pixel_ratio(gray <= 16),
            "bright_pixel_ratio": _pixel_ratio(gray >= 239),
            "clipped_pixel_ratio": _pixel_ratio((gray <= 2) | (gray >= 253)),
            "noise_score": _noise_score(gray),
            "mono_color_score": _mono_color_score(rgb),
        }


def _laplacian_variance(array: NDArray[np.float64]) -> float:
    """使用轻量 numpy 卷积近似拉普拉斯方差。"""
    if array.shape[0] < 3 or array.shape[1] < 3:
        return 0.0
    center = array[1:-1, 1:-1] * -4
    laplacian = center + array[:-2, 1:-1] + array[2:, 1:-1] + array[1:-1, :-2] + array[1:-1, 2:]
    return float(laplacian.var())


def _pixel_ratio(mask: NDArray[np.bool_]) -> float:
    """计算布尔掩码中的命中像素比例。"""
    if mask.size == 0:
        return 0.0
    return float(mask.mean())


def _noise_score(array: NDArray[np.float64]) -> float:
    """用相邻像素差估计轻量噪声风险，返回 0 到 1 附近的分数。"""
    if array.shape[0] < 2 or array.shape[1] < 2:
        return 0.0
    horizontal = np.abs(np.diff(array, axis=1)).mean()
    vertical = np.abs(np.diff(array, axis=0)).mean()
    return float(min(1.0, (horizontal + vertical) / 510.0))


def _mono_color_score(rgb: NDArray[np.float64]) -> float:
    """估计图片是否接近单色，1 表示高度单色。"""
    if rgb.size == 0:
        return 0.0
    flattened = rgb.reshape(-1, 3)
    channel_std = float(flattened.std(axis=0).mean())
    return float(max(0.0, min(1.0, 1.0 - channel_std / 64.0)))
