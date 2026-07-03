from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset, DatasetImage
from image_gallery.operators.backends.base import BackendAdapter, BackendOperatorRequest, BackendResult


class PillowMetadataBackend(BackendAdapter):
    """基于 Pillow 的图片基础元数据后端。"""

    name = "pillow_metadata_backend"

    def compute_parameters(
        self,
        dataset: Dataset,
        parameter_table: pd.DataFrame,
        requests: list[BackendOperatorRequest],
        artifacts_dir: str | Path,
    ) -> BackendResult:
        """计算解码和尺寸相关参数。"""
        rows: list[dict[str, object]] = []
        for image in dataset.iter_images():
            metadata = read_image_metadata(image)
            rows.append({"image_id": image.image_id, **metadata})
        return BackendResult(
            parameter_updates=pd.DataFrame(rows),
            relation_updates={},
            artifact_refs={},
        )


def read_image_metadata(image: DatasetImage) -> dict[str, object]:
    """读取单张图片的基础元数据。"""
    try:
        loaded = image.read_image()
        return {
            "width": int(loaded.width),
            "height": int(loaded.height),
            "format": str(loaded.format or ""),
            "decode_ok": True,
            "decode_error": "",
        }
    except Exception as exc:
        return {
            "width": pd.NA,
            "height": pd.NA,
            "format": "",
            "decode_ok": False,
            "decode_error": str(exc),
        }
