"""仓库内固定本地测试数据集的装配 helper。"""

from pathlib import Path
from typing import cast

import pandas as pd

from image_gallery.dataset import Dataset
from image_gallery.storage.uri import make_file_image_uri

SAMPLE_10_SIZE = 10


def get_sample_10_fixture_path() -> Path:
    """返回固定 sample_10 fixture 的 Parquet 路径。"""
    return Path(__file__).parents[1] / "fixtures" / "sample_10" / "raw.parquet"


def load_sample_10_frame() -> pd.DataFrame:
    """读取持久化的 sample_10 数据表。"""
    return pd.read_parquet(get_sample_10_fixture_path())


def materialize_sample_10_dataset(output_dir: Path) -> Dataset:
    """把 fixture 相对图片引用解析为当前 checkout 的本地 Dataset。"""
    fixture_path = get_sample_10_fixture_path()
    frame = load_sample_10_frame().copy()
    frame["image_uri"] = frame["image_uri"].map(
        lambda uri: make_file_image_uri(fixture_path.parent, str(uri)),
    )
    return Dataset.write(cast(pd.DataFrame, frame), str(output_dir / "raw.parquet"))
