import pandas as pd

from image_gallery.schemas.raw import RawDatasetSchema


def validate_raw_dataset(frame: pd.DataFrame) -> None:
    """校验 raw Dataset 最小字段存在性。"""
    missing = [column for column in RawDatasetSchema.required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required raw dataset columns: {missing}")
