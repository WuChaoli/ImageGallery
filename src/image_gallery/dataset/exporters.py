from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from image_gallery.dataset.io import DatasetExportResult


@dataclass(frozen=True)
class TabularDatasetExporter:
    """把 Dataset 表格导出为 Parquet、CSV 或 JSONL。"""

    output_path: str | Path
    drop_source_uri: bool = True

    def export(self, dataset: object) -> DatasetExportResult:
        """导出 Dataset 表格，默认移除 source_uri 追溯字段。"""
        from image_gallery.dataset.dataset import Dataset

        if not isinstance(dataset, Dataset):
            raise TypeError("dataset must be a Dataset")

        frame = dataset.to_frame()
        if self.drop_source_uri and "source_uri" in frame.columns:
            frame = frame.drop(columns=["source_uri"])

        output_path = str(self.output_path)
        Dataset.write(frame, output_path, storage=dataset.storage)
        return DatasetExportResult(output_path=output_path)
