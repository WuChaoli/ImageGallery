"""新平台隔离的 Iceberg FileIO adapters。"""

from fsspec.implementations.local import LocalFileSystem
from pyiceberg.io.fsspec import FsspecFileIO


class IsolatedFsspecFileIO(FsspecFileIO):  # pyright: ignore[reportUntypedBaseClass]
    """避免 fsspec 全局实例缓存污染本地 Iceberg 写入配置。"""

    def __init__(self, properties: dict[str, str]) -> None:
        """为每个 FileIO 生命周期创建可自动建目录的本地客户端。"""
        super().__init__(properties)
        self._scheme_to_fs["file"] = lambda _: LocalFileSystem(auto_mkdir=True, skip_instance_cache=True)
