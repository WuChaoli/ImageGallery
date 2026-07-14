from pathlib import Path
from typing import Any, cast

import pandas as pd

from image_gallery.dataset import Dataset
from image_gallery.importers.config import SourceRecord


class DatasetParser:
    """从已有 Dataset 文件解析待导入图片清单。"""

    def __init__(
        self,
        dataset_path: str | Path,
        image_uri_column: str = "image_uri",
        source_uri_column: str = "source_uri",
    ) -> None:
        self.dataset_path = str(dataset_path)
        self.image_uri_column = image_uri_column
        self.source_uri_column = source_uri_column

    def parse(self) -> list[SourceRecord]:
        """从指定图片地址列生成 SourceRecord。"""
        if not self.image_uri_column:
            raise ValueError("image_uri_column must not be empty")
        if not self.source_uri_column:
            raise ValueError("source_uri_column must not be empty")

        frame = Dataset.load(self.dataset_path).to_frame()
        if self.image_uri_column not in frame.columns:
            raise ValueError(f"missing image uri column: {self.image_uri_column}")

        records: list[SourceRecord] = []
        for row in cast(list[dict[str, object]], frame.to_dict("records")):
            image_uri = str(row[self.image_uri_column])
            source_value = row.get(self.source_uri_column)
            source_uri = image_uri if _is_empty_value(source_value) else str(source_value)
            path = Path(image_uri)
            records.append(
                SourceRecord(
                    source_uri=source_uri,
                    source_type="dataset",
                    source_file_name=path.name,
                    source_relative_path=path.name,
                    local_path=path if path.is_absolute() else None,
                )
            )
        return records


def _is_empty_value(value: object) -> bool:
    """判断 Dataset 单元格是否应视为缺失。"""
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    return bool(pd.isna(cast(Any, value)))
