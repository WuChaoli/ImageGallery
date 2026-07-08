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


class ImageBorderComputer(ParameterComputer):
    """检测图片四周的简单纯色边框或留白。"""

    name = "image_border_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"border_padding_ratio", "border_padding_sides", "border_padding_color"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """生产边框留白参数。"""
        if request.image_batch is None:
            raise ValueError("ImageBorderComputer requires image_batch")

        requested = set(request.requested_parameters)
        produced = requested & set(self.produced_parameters)
        rows: list[dict[str, object]] = []
        for item in request.image_batch.items:
            values = self._values_for_item(item)
            row: dict[str, object] = {"image_id": item.image_id}
            for parameter in sorted(produced):
                row[parameter] = values[parameter]
            rows.append(row)

        manifest = {
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
        """把单张图片转换为边框留白参数。"""
        if item.error or item.image is None:
            return {
                "border_padding_ratio": pd.NA,
                "border_padding_sides": "",
                "border_padding_color": "unknown",
            }
        rgb = np.asarray(item.image.convert("RGB"), dtype=np.float64)
        ratio, sides, color = _detect_border(rgb)
        return {
            "border_padding_ratio": ratio,
            "border_padding_sides": ",".join(sides),
            "border_padding_color": color,
        }


def _detect_border(rgb: NDArray[np.float64]) -> tuple[float, list[str], str]:
    """检测四周连续纯色边框，返回面积占比、边列表和颜色类别。"""
    if rgb.ndim != 3 or rgb.shape[0] == 0 or rgb.shape[1] == 0:
        return 0.0, [], "unknown"

    height, width, _ = rgb.shape
    edge_color = _edge_median_color(rgb)
    tolerance = 8.0
    row_matches = np.abs(rgb - edge_color).max(axis=2) <= tolerance
    top = _leading_true_count(row_matches.all(axis=1))
    bottom = _leading_true_count(row_matches[::-1].all(axis=1))
    left = _leading_true_count(row_matches.all(axis=0))
    right = _leading_true_count(row_matches[:, ::-1].all(axis=0))
    if top + bottom >= height or left + right >= width:
        return 0.0, [], "unknown"

    min_pixels = max(2, int(min(height, width) * 0.08))
    sides: list[str] = []
    if top >= min_pixels:
        sides.append("top")
    if bottom >= min_pixels:
        sides.append("bottom")
    if left >= min_pixels:
        sides.append("left")
    if right >= min_pixels:
        sides.append("right")
    if not sides:
        return 0.0, [], "unknown"

    vertical_area = (top if "top" in sides else 0) * width + (bottom if "bottom" in sides else 0) * width
    horizontal_height = height - (top if "top" in sides else 0) - (bottom if "bottom" in sides else 0)
    horizontal_area = horizontal_height * ((left if "left" in sides else 0) + (right if "right" in sides else 0))
    ratio = float((vertical_area + horizontal_area) / (height * width))
    return ratio, sides, _classify_border_color(edge_color)


def _edge_median_color(rgb: NDArray[np.float64]) -> NDArray[np.float64]:
    """用四条边的中位颜色估计边框主色。"""
    top = rgb[0, :, :]
    bottom = rgb[-1, :, :]
    left = rgb[:, 0, :]
    right = rgb[:, -1, :]
    edge_pixels = np.concatenate([top, bottom, left, right], axis=0)
    return np.median(edge_pixels, axis=0)


def _leading_true_count(values: NDArray[np.bool_]) -> int:
    """计算从开头开始连续为 True 的数量。"""
    count = 0
    for value in values.tolist():
        if not value:
            break
        count += 1
    return count


def _classify_border_color(color: NDArray[np.float64]) -> str:
    """把边框颜色粗略归类。"""
    mean = float(color.mean())
    spread = float(color.max() - color.min())
    if mean >= 240 and spread <= 16:
        return "white"
    if mean <= 16 and spread <= 16:
        return "black"
    if spread <= 16:
        return "solid"
    return "unknown"
