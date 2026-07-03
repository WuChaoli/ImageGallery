from pathlib import Path

import pandas as pd

from image_gallery.cleaning.errors import BackendExecutionError
from image_gallery.dataset import Dataset
from image_gallery.operators.backends.base import BackendAdapter, BackendOperatorRequest, BackendResult


class FastdupSimilarityBackend(BackendAdapter):
    """fastdup 相似度与聚类后端边界。"""

    name = "fastdup_similarity_backend"

    def compute_parameters(
        self,
        dataset: Dataset,
        parameter_table: pd.DataFrame,
        requests: list[BackendOperatorRequest],
        artifacts_dir: str | Path,
    ) -> BackendResult:
        """提示用户安装 fastdup 依赖后再使用近重复能力。"""
        try:
            import fastdup  # noqa: F401
        except ModuleNotFoundError as exc:
            raise BackendExecutionError(
                "fastdup is not installed; install image_gallery[fastdup] to use "
                "duplicate.near_duplicate_check, distribution.outlier_check, or distribution.cluster_check"
            ) from exc
        raise BackendExecutionError("fastdup backend normalization is not implemented in stage 4")


def build_fastdup_input(parameter_table: pd.DataFrame, work_dir: str | Path) -> Path:
    """把平台 image_uri 列转换为 fastdup 可读取输入。"""
    work_path = Path(work_dir)
    work_path.mkdir(parents=True, exist_ok=True)
    input_path = work_path / "fastdup_input.txt"
    input_path.write_text("\n".join(parameter_table["image_uri"].astype(str).tolist()), encoding="utf-8")
    return input_path


def normalize_fastdup_outputs(output_dir: str | Path) -> BackendResult:
    """阶段 4 暂不实现 fastdup 原始输出归一化。"""
    raise BackendExecutionError(f"fastdup output normalization is not implemented: {output_dir}")
