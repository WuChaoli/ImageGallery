import numpy as np
import pandas as pd

from image_gallery.operators.computers.base import (
    ComputeStage,
    ImageBatchItem,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)


class ImageQualityComputer(ParameterComputer):
    """基于共享解码图片生产基础质量参数。"""

    name = "image_quality_computer"
    stage = ComputeStage.IMAGE_BATCH
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

        manifest = {
            parameter: {
                "computer": self.name,
                "stage": self.stage.value,
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


def _laplacian_variance(array: np.ndarray) -> float:
    """使用轻量 numpy 卷积近似拉普拉斯方差。"""
    if array.shape[0] < 3 or array.shape[1] < 3:
        return 0.0
    center = array[1:-1, 1:-1] * -4
    laplacian = center + array[:-2, 1:-1] + array[2:, 1:-1] + array[1:-1, :-2] + array[1:-1, 2:]
    return float(laplacian.var())
