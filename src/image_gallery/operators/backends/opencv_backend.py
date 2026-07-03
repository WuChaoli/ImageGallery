from pathlib import Path
from typing import Any

import pandas as pd

from image_gallery.dataset import Dataset, DatasetImage
from image_gallery.operators.backends.base import BackendAdapter, BackendOperatorRequest, BackendResult


class OpenCVQualityBackend(BackendAdapter):
    """基于 OpenCV 或 Pillow 兜底实现的质量参数后端。"""

    name = "opencv_quality_backend"

    def compute_parameters(
        self,
        dataset: Dataset,
        parameter_table: pd.DataFrame,
        requests: list[BackendOperatorRequest],
        artifacts_dir: str | Path,
    ) -> BackendResult:
        """计算 blur、brightness、contrast 参数。"""
        requested_columns = {column for request in requests for column in request.parameter_columns}
        rows: list[dict[str, object]] = []
        for image in dataset.iter_images():
            result: dict[str, object] = {"image_id": image.image_id}
            if "blur_score" in requested_columns:
                result["blur_score"] = compute_blur_score(image)
            if "brightness_score" in requested_columns:
                result["brightness_score"] = compute_brightness_score(image)
            if "contrast_score" in requested_columns:
                result["contrast_score"] = compute_contrast_score(image)
            rows.append(result)
        return BackendResult(
            parameter_updates=pd.DataFrame(rows),
            relation_updates={},
            artifact_refs={},
        )


def compute_blur_score(image: DatasetImage) -> float:
    """计算单张图片的模糊分数，分数越高通常越清晰。"""
    gray = _read_grayscale_values(image)
    try:
        import cv2

        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except ModuleNotFoundError:
        laplacian = _laplacian_values(gray)
        return float(laplacian.var())


def compute_brightness_score(image: DatasetImage) -> float:
    """计算单张图片的平均亮度。"""
    gray = _read_grayscale_values(image)
    return float(gray.mean())


def compute_contrast_score(image: DatasetImage) -> float:
    """计算单张图片的亮度标准差作为对比度。"""
    gray = _read_grayscale_values(image)
    return float(gray.std())


def _read_grayscale_values(image: DatasetImage) -> Any:
    """读取灰度像素数组。"""
    import numpy as np

    loaded = image.read_image()
    return np.asarray(loaded.convert("L"), dtype="float64")


def _laplacian_values(gray: Any) -> Any:
    """用 NumPy 计算简化 Laplacian。"""
    import numpy as np

    padded = np.pad(gray, 1, mode="edge")
    return (
        -4 * padded[1:-1, 1:-1]
        + padded[:-2, 1:-1]
        + padded[2:, 1:-1]
        + padded[1:-1, :-2]
        + padded[1:-1, 2:]
    )
