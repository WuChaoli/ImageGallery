"""运行产物存储抽象层，支持 memory / temporary / disk 三种模式。"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class RunStore(Protocol):
    """运行产物存储协议。

    实现类需支持 DataFrame 和 JSON 数据的读写，以及运行目录的清理。
    """

    def run_dir(self) -> Path:
        """返回当前运行的工作目录路径。"""
        ...

    def write_table(self, name: str, frame: pd.DataFrame) -> Path:
        """将 DataFrame 写入 Parquet 文件并返回路径。"""
        ...

    def read_table(self, name: str) -> pd.DataFrame:
        """从 Parquet 文件读取 DataFrame。"""
        ...

    def write_json(self, name: str, data: object) -> Path:
        """将数据写入 JSON 文件并返回路径。"""
        ...

    def read_json(self, name: str) -> dict[str, object]:
        """从 JSON 文件读取数据。"""
        ...

    def materialize_dataset(self, frame: pd.DataFrame) -> Path:
        """将数据集 DataFrame 写入运行目录并返回路径。"""
        ...

    def cleanup(self) -> None:
        """清理运行产物。"""
        ...


class MemoryRunStore:
    """内存模式存储，无文件系统 IO。

    适用于不涉及 artifact 文件的算子测试。
    """

    def __init__(self) -> None:
        """初始化内存存储。"""
        self._tables: dict[str, pd.DataFrame] = {}
        self._jsons: dict[str, object] = {}
        self._dataset: pd.DataFrame | None = None

    def run_dir(self) -> Path:
        """返回占位路径（内存模式无实际目录）。"""
        return Path("<memory>")

    def write_table(self, name: str, frame: pd.DataFrame) -> Path:
        """将 DataFrame 保存到内存字典。"""
        self._tables[name] = frame.copy()
        return Path(f"<memory>/{name}.parquet")

    def read_table(self, name: str) -> pd.DataFrame:
        """从内存字典读取 DataFrame。"""
        if name not in self._tables:
            raise KeyError(f"table not found in memory store: {name!r}")
        return self._tables[name].copy()

    def write_json(self, name: str, data: object) -> Path:
        """将 JSON 数据保存到内存字典。"""
        self._jsons[name] = data
        return Path(f"<memory>/{name}.json")

    def read_json(self, name: str) -> dict[str, object]:
        """从内存字典读取 JSON 数据。"""
        if name not in self._jsons:
            raise KeyError(f"json not found in memory store: {name!r}")
        data = self._jsons[name]
        if not isinstance(data, dict):
            raise TypeError(f"stored json {name!r} is not a dict")
        return dict(data)

    def materialize_dataset(self, frame: pd.DataFrame) -> Path:
        """将数据集保存到内存。"""
        self._dataset = frame.copy()
        return Path("<memory>/parameter_table.parquet")

    def cleanup(self) -> None:
        """清空内存字典。"""
        self._tables.clear()
        self._jsons.clear()
        self._dataset = None


class TemporaryRunStore:
    """临时目录模式存储，cleanup 时自动删除。"""

    def __init__(self) -> None:
        """创建临时目录。"""
        self._tmp_dir = Path(tempfile.mkdtemp(prefix="image_gallery_run_"))

    def run_dir(self) -> Path:
        """返回临时目录路径。"""
        return self._tmp_dir

    def write_table(self, name: str, frame: pd.DataFrame) -> Path:
        """将 DataFrame 写入临时目录中的 Parquet 文件。"""
        path = self._tmp_dir / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        return path

    def read_table(self, name: str) -> pd.DataFrame:
        """从临时目录中的 Parquet 文件读取 DataFrame。"""
        path = self._tmp_dir / f"{name}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"table not found: {path}")
        return pd.read_parquet(path)

    def write_json(self, name: str, data: object) -> Path:
        """将数据写入临时目录中的 JSON 文件。"""
        path = self._tmp_dir / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def read_json(self, name: str) -> dict[str, object]:
        """从临时目录中的 JSON 文件读取数据。"""
        path = self._tmp_dir / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"json not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError(f"json {name!r} is not a dict")
        return payload

    def materialize_dataset(self, frame: pd.DataFrame) -> Path:
        """将数据集写入临时目录。"""
        path = self._tmp_dir / "parameter_table.parquet"
        frame.to_parquet(path, index=False)
        return path

    def cleanup(self) -> None:
        """删除临时目录及其内容。"""
        if self._tmp_dir.exists():
            shutil.rmtree(self._tmp_dir)


class DiskRunStore:
    """磁盘持久化模式，封装 ``cache_root / run_id`` 路径逻辑。"""

    def __init__(self, cache_root: str | Path, run_id: str) -> None:
        """初始化磁盘存储。

        Args:
            cache_root: 缓存根目录。
            run_id: 运行 ID。
        """
        self._run_dir = Path(cache_root) / run_id
        self._run_dir.mkdir(parents=True, exist_ok=True)

    def run_dir(self) -> Path:
        """返回运行目录路径。"""
        return self._run_dir

    def write_table(self, name: str, frame: pd.DataFrame) -> Path:
        """将 DataFrame 写入运行目录中的 Parquet 文件。"""
        path = self._run_dir / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        return path

    def read_table(self, name: str) -> pd.DataFrame:
        """从运行目录中的 Parquet 文件读取 DataFrame。"""
        path = self._run_dir / f"{name}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"table not found: {path}")
        return pd.read_parquet(path)

    def write_json(self, name: str, data: object) -> Path:
        """将数据写入运行目录中的 JSON 文件。"""
        path = self._run_dir / f"{name}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return path

    def read_json(self, name: str) -> dict[str, object]:
        """从运行目录中的 JSON 文件读取数据。"""
        path = self._run_dir / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"json not found: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError(f"json {name!r} is not a dict")
        return payload

    def materialize_dataset(self, frame: pd.DataFrame) -> Path:
        """将数据集写入运行目录。"""
        path = self._run_dir / "parameter_table.parquet"
        frame.to_parquet(path, index=False)
        return path

    def cleanup(self) -> None:
        """删除运行目录及其内容。"""
        if self._run_dir.exists():
            shutil.rmtree(self._run_dir)
