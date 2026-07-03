import hashlib
from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset, DatasetImage
from image_gallery.operators.backends.base import BackendAdapter, BackendOperatorRequest, BackendResult


class ImageHashBackend(BackendAdapter):
    """图片 hash 后端。"""

    name = "image_hash_backend"

    def compute_parameters(
        self,
        dataset: Dataset,
        parameter_table: pd.DataFrame,
        requests: list[BackendOperatorRequest],
        artifacts_dir: str | Path,
    ) -> BackendResult:
        """计算内容 hash、感知 hash 和完全重复分组。"""
        rows: list[dict[str, object]] = []
        for image in dataset.iter_images():
            rows.append(
                {
                    "image_id": image.image_id,
                    "content_hash": compute_content_hash(image),
                    "phash": compute_phash(image),
                }
            )
        updates = assign_exact_duplicate_groups(pd.DataFrame(rows))
        return BackendResult(parameter_updates=updates, relation_updates={}, artifact_refs={})


def compute_content_hash(image: DatasetImage) -> str:
    """计算图片文件内容 hash。"""
    return hashlib.sha256(image.read_bytes()).hexdigest()


def compute_phash(image: DatasetImage) -> str:
    """计算轻量感知 hash。"""
    loaded = image.read_image()
    gray = loaded.convert("L").resize((8, 8))
    values = list(gray.tobytes())
    average = sum(values) / len(values)
    bits = "".join("1" if value >= average else "0" for value in values)
    return f"{int(bits, 2):016x}"


def assign_exact_duplicate_groups(frame: pd.DataFrame) -> pd.DataFrame:
    """基于 content_hash 生成完全重复分组。"""
    result = frame.copy()
    duplicate_hashes = result["content_hash"][result["content_hash"].duplicated(keep=False)]
    group_by_hash = {
        content_hash: f"exact-{index:06d}"
        for index, content_hash in enumerate(sorted(duplicate_hashes.unique()), start=1)
    }
    result["exact_duplicate_group_id"] = result["content_hash"].map(group_by_hash).fillna("")
    return result
