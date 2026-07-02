from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from image_gallery.dataset.fingerprint import dataframe_fingerprint


@dataclass(frozen=True)
class Dataset:
    """数据集文件的轻量封装，不表达 raw、clean、dropped、full 阶段语义。"""

    dataset_uri: str
    format: str = "parquet"

    @classmethod
    def from_uri(cls, dataset_uri: str) -> "Dataset":
        return cls(dataset_uri=dataset_uri, format=_format_from_uri(dataset_uri))

    @classmethod
    def write(cls, data: pd.DataFrame, output_uri: str) -> "Dataset":
        output_path = Path(output_uri)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        file_format = _format_from_uri(output_uri)
        if file_format == "parquet":
            data.to_parquet(output_path, index=False)
        elif file_format == "csv":
            data.to_csv(output_path, index=False)
        elif file_format == "jsonl":
            data.to_json(output_path, orient="records", lines=True, force_ascii=False)
        else:
            raise ValueError(f"unsupported dataset format: {file_format}")
        return cls(dataset_uri=output_uri, format=file_format)

    def to_frame(self, columns: list[str] | None = None) -> pd.DataFrame:
        frame = _read_frame(self.dataset_uri, self.format)
        if columns is not None:
            return frame[columns]
        return frame

    def scan(self, columns: list[str] | None = None, filters: dict[str, object] | None = None) -> pd.DataFrame:
        """读取数据集并按等值条件过滤，供后续模块做轻量扫描。"""
        frame = self.to_frame()
        if filters:
            for column, value in filters.items():
                frame = frame[frame[column] == value]
        if columns is not None:
            return frame[columns]
        return frame

    def preview(self, limit: int = 100) -> pd.DataFrame:
        return self.to_frame().head(limit)

    def count(self) -> int:
        return len(self.to_frame())

    def validate_readable(self) -> None:
        """确认数据集文件存在且能被当前格式读取。"""
        if not Path(self.dataset_uri).exists():
            raise FileNotFoundError(self.dataset_uri)
        self.preview(limit=1)

    def fingerprint(self) -> str:
        return dataframe_fingerprint(self.to_frame())

    def export(self, output_dataset_uri: str, address_policy: str = "keep") -> "Dataset":
        """导出数据集；默认保留 image_uri 并移除 source_uri。"""
        if address_policy != "keep":
            raise ValueError(f"unsupported address_policy: {address_policy}")
        frame = self.to_frame()
        if "source_uri" in frame.columns:
            frame = frame.drop(columns=["source_uri"])
        return Dataset.write(frame, output_dataset_uri)


def _format_from_uri(dataset_uri: str) -> str:
    suffix = Path(dataset_uri).suffix.lower()
    if suffix == ".parquet":
        return "parquet"
    if suffix == ".csv":
        return "csv"
    if suffix in {".jsonl", ".json"}:
        return "jsonl"
    raise ValueError(f"unsupported dataset extension: {suffix}")


def _read_frame(dataset_uri: str, file_format: str) -> pd.DataFrame:
    if file_format == "parquet":
        return pd.read_parquet(dataset_uri)
    if file_format == "csv":
        return pd.read_csv(dataset_uri)
    if file_format == "jsonl":
        return pd.read_json(dataset_uri, lines=True)
    raise ValueError(f"unsupported dataset format: {file_format}")
