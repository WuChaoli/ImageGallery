"""Dataset helpers for notebook validation flows."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset
from notebooks._helpers.paths import get_repo_root
from notebooks._helpers.storage import load_minio_storage


def get_default_minio_sample_1000_raw_path() -> Path:
    """Return the raw parquet path for the default MinIO sample_1000 dataset."""
    repo_root = get_repo_root()
    relative_path = Path("datasets") / "sample_1000" / "raw.parquet"
    worktree_dataset_path = repo_root / relative_path
    if worktree_dataset_path.exists():
        return worktree_dataset_path

    # 隔离 worktree 通常不携带真实数据集，回退到主 checkout 的同名数据路径。
    if repo_root.parent.name == ".worktrees":
        main_dataset_path = repo_root.parent.parent / relative_path
        if main_dataset_path.exists():
            return main_dataset_path
    return worktree_dataset_path


def load_default_minio_sample_1000_dataset() -> Dataset:
    """Load the sample_1000 dataset with MinIO-backed image access."""
    raw_path = get_default_minio_sample_1000_raw_path()
    if not raw_path.exists():
        raise RuntimeError(f"sample raw dataset not found: {raw_path}")
    return Dataset.load(str(raw_path), storage=load_minio_storage())


def load_default_minio_sample_1000_frame() -> pd.DataFrame:
    """Load the sample_1000 raw parquet as a dataframe."""
    raw_path = get_default_minio_sample_1000_raw_path()
    if not raw_path.exists():
        raise RuntimeError(f"sample raw dataset not found: {raw_path}")
    return pd.read_parquet(raw_path)
