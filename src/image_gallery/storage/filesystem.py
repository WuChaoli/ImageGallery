import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from image_gallery.storage.base import Storage
from image_gallery.storage.errors import ObjectAlreadyExistsError, ObjectNotFoundError, StorageConnectionError
from image_gallery.storage.uri import (
    is_file_image_uri_under_root,
    make_file_image_uri,
    require_file_image_uri_under_root,
    resolve_object_path,
)


@dataclass
class FileSystemStorage(Storage):
    """本地或挂载文件系统 storage。"""

    storage_name: str
    root: str | Path | None = None
    _connected_root: Path | None = field(default=None, init=False, repr=False)

    def connect(self, root: str | Path | None = None) -> "FileSystemStorage":
        """连接本地 storage 根目录，并验证目录可读写。"""
        root = root or self.root
        if root is None:
            raise StorageConnectionError("filesystem storage requires root")
        if not isinstance(root, (str, Path)):
            raise StorageConnectionError("filesystem root must be a string or Path")

        root_path = Path(root).expanduser().resolve()
        if root_path.exists() and not root_path.is_dir():
            raise StorageConnectionError(f"storage root is not a directory: {root_path}")

        try:
            root_path.mkdir(parents=True, exist_ok=True)
            probe_path = root_path / f".image_gallery_probe_{uuid.uuid4().hex}"
            probe_path.write_bytes(b"ok")
            if probe_path.read_bytes() != b"ok":
                raise StorageConnectionError(f"storage root read/write probe failed: {root_path}")
            probe_path.unlink()
        except OSError as exc:
            raise StorageConnectionError(f"storage root is not readable and writable: {root_path}") from exc

        self.root = root_path
        self._connected_root = root_path
        return self

    def _path(self, object_path: str) -> Path:
        """把 object_path 解析为受根目录约束的本地绝对路径。"""
        return resolve_object_path(self._require_connected_root(), object_path)

    def _require_connected_root(self) -> Path:
        """返回已连接根目录；未连接时抛出统一 storage 连接错误。"""
        if self._connected_root is None:
            raise StorageConnectionError(f"storage is not connected: {self.storage_name}")
        return self._connected_root

    def _write_bytes(self, object_path: str, data: bytes, overwrite: bool = False) -> str:
        """写入本地文件并返回 file:// image_uri。"""
        path = self._path(object_path)
        if path.exists() and not overwrite:
            raise ObjectAlreadyExistsError(f"object already exists: {object_path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.make_image_uri(object_path)

    def _read_bytes(self, object_path: str) -> bytes:
        """读取本地文件 bytes，不存在时抛出 ObjectNotFoundError。"""
        path = self._path(object_path)
        if not path.exists():
            raise ObjectNotFoundError(f"object not found: {object_path}")
        return path.read_bytes()

    def exists(self, object_path: str) -> bool:
        """检查本地对象路径是否存在。"""
        return self._path(object_path).exists()

    def delete(self, object_path: str) -> None:
        """删除本地对象，不存在时抛出 ObjectNotFoundError。"""
        path = self._path(object_path)
        if not path.exists():
            raise ObjectNotFoundError(f"object not found: {object_path}")
        path.unlink()

    def copy(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
        """在同一 storage 根目录内复制对象并返回目标 image_uri。"""
        src = self._path(src_object_path)
        dst = self._path(dst_object_path)
        if not src.exists():
            raise ObjectNotFoundError(f"object not found: {src_object_path}")
        if dst.exists() and not overwrite:
            raise ObjectAlreadyExistsError(f"object already exists: {dst_object_path}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return self.make_image_uri(dst_object_path)

    def move(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
        """在同一 storage 根目录内移动对象并返回目标 image_uri。"""
        image_uri = self.copy(src_object_path, dst_object_path, overwrite)
        self.delete(src_object_path)
        return image_uri

    def make_image_uri(self, object_path: str) -> str:
        """为本地对象生成可写入数据集的 file:// image_uri。"""
        return make_file_image_uri(self._require_connected_root(), object_path)

    def contains_image_uri(self, image_uri: str) -> bool:
        """判断 file:// image_uri 是否落在当前 storage 根目录下。"""
        return is_file_image_uri_under_root(self._require_connected_root(), image_uri)

    def validate_output_path(self, output_path: str) -> Path:
        """把 file:// 输出地址校验并解析为当前根目录内路径。"""
        return require_file_image_uri_under_root(self._require_connected_root(), output_path)
