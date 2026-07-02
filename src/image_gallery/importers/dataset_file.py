from pathlib import Path

from image_gallery.dataset import Dataset
from image_gallery.importers.config import SourceRecord


class DatasetFileReader:
    """从已有 Dataset 文件读取待导入图片清单。"""

    def __init__(self, dataset_path: str) -> None:
        self.dataset_path = dataset_path

    def read(self) -> list[SourceRecord]:
        """从 image_uri 列生成 SourceRecord，source_uri 缺失时回退为 image_uri。"""
        frame = Dataset.from_path(self.dataset_path).to_frame()
        records: list[SourceRecord] = []
        for row in frame.to_dict("records"):
            image_uri = str(row["image_uri"])
            source_uri = str(row.get("source_uri") or image_uri)
            path = Path(image_uri)
            records.append(
                SourceRecord(
                    source_uri=source_uri,
                    source_type="dataset_file",
                    source_file_name=path.name,
                    source_relative_path=path.name,
                    local_path=path if path.exists() or path.is_absolute() else None,
                )
            )
        return records
