from pathlib import Path

import pandas as pd


def format_from_path(dataset_path: str) -> str:
    """根据数据集路径后缀推导文件格式。"""
    suffix = Path(dataset_path).suffix.lower()
    if suffix == ".parquet":
        return "parquet"
    if suffix == ".csv":
        return "csv"
    if suffix in {".jsonl", ".json"}:
        return "jsonl"
    raise ValueError(f"unsupported dataset extension: {suffix}")


def read_frame(dataset_path: str, file_format: str) -> pd.DataFrame:
    """按指定格式读取数据集文件为 DataFrame。"""
    if file_format == "parquet":
        return pd.read_parquet(dataset_path)
    if file_format == "csv":
        return pd.read_csv(dataset_path)
    if file_format == "jsonl":
        return pd.read_json(dataset_path, lines=True)
    raise ValueError(f"unsupported dataset format: {file_format}")


def write_frame(data: pd.DataFrame, output_path: str | Path, file_format: str) -> None:
    """按指定格式写出 DataFrame。"""
    if file_format == "parquet":
        data.to_parquet(output_path, index=False)
        return
    if file_format == "csv":
        data.to_csv(output_path, index=False)
        return
    if file_format == "jsonl":
        data.to_json(output_path, orient="records", lines=True, force_ascii=False)
        return
    raise ValueError(f"unsupported dataset format: {file_format}")
