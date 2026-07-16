"""依赖 MinIO sample_1000 的慢速真实数据验收。"""

from __future__ import annotations

from pathlib import Path

import pytest
from notebooks._helpers.cleaning_configs import get_cleaning_v3_first_batch_operator_configs
from notebooks._helpers.datasets import (
    load_default_minio_sample_1000_dataset,
    load_default_minio_sample_1000_frame,
)

from image_gallery.cleaning import BasicCleaner

pytestmark = [pytest.mark.slow, pytest.mark.real_dataset]


@pytest.fixture(scope="module")
def sample_1000_dataset():
    """加载真实 sample_1000，不可用时明确跳过。"""
    try:
        return load_default_minio_sample_1000_dataset()
    # 真实数据环境可能在网络、凭据或 MinIO 任一边界不可用。
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"sample_1000 real dataset unavailable: {exc}")


def test_sample_1000_real_dataset_contract(sample_1000_dataset) -> None:
    frame = load_default_minio_sample_1000_frame()
    assert len(frame) == 1000
    assert {"image_id", "image_uri"}.issubset(frame.columns)
    assert sample_1000_dataset.read_image_bytes(str(frame.iloc[0]["image_uri"]))


def test_first_batch_real_run_on_sample_1000(sample_1000_dataset, tmp_path: Path) -> None:
    result = BasicCleaner(get_cleaning_v3_first_batch_operator_configs()).run(
        sample_1000_dataset,
        label="sample-1000-real-acceptance",
    )

    assert result.status() == "completed"
    assert len(result.export("full", tmp_path / "full.parquet").to_frame()) == 1000
