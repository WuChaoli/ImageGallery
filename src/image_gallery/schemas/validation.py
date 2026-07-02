import pandas as pd

from image_gallery.schemas.raw import RawDatasetSchema


def validate_raw_dataset(frame: pd.DataFrame) -> None:
    """校验 raw Dataset 最小字段存在性。"""
    missing = [column for column in RawDatasetSchema.required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required raw dataset columns: {missing}")
    _validate_tags(frame["tags"])


def _validate_tags(tags_series: pd.Series) -> None:
    """校验层级 tags 列的最小结构，不维护合法标签字典。"""
    for row_index, tags in tags_series.items():
        if not isinstance(tags, (list, tuple)):
            raise ValueError(f"invalid raw dataset tags at row {row_index}: tags must be a list or tuple")
        for tag_path in tags:
            if not _is_valid_tag_path(tag_path):
                raise ValueError(f"invalid raw dataset tags at row {row_index}: {tag_path!r}")


def _is_valid_tag_path(tag_path: object) -> bool:
    """判断 tag path 是否满足非空、无首尾斜杠、无空层级的最小规则。"""
    if not isinstance(tag_path, str) or not tag_path:
        return False
    if tag_path.startswith("/") or tag_path.endswith("/"):
        return False
    return all(part for part in tag_path.split("/"))
