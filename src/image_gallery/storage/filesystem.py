import shutil
from dataclasses import dataclass
from pathlib import Path

from image_gallery.storage.base import Storage
from image_gallery.storage.errors import ObjectAlreadyExistsError, ObjectNotFoundError
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
    root: str | Path

    def connect(self) -> "FileSystemStorage":
        Path(self.root).expanduser().resolve().mkdir(parents=True, exist_ok=True)
        return self

    def _path(self, object_path: str) -> Path:
        return resolve_object_path(self.root, object_path)

    def write_bytes(self, object_path: str, data: bytes, overwrite: bool = False) -> str:
        path = self._path(object_path)
        if path.exists() and not overwrite:
            raise ObjectAlreadyExistsError(f"object already exists: {object_path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.make_image_uri(object_path)

    def read_bytes(self, object_path: str) -> bytes:
        path = self._path(object_path)
        if not path.exists():
            raise ObjectNotFoundError(f"object not found: {object_path}")
        return path.read_bytes()

    def exists(self, object_path: str) -> bool:
        return self._path(object_path).exists()

    def delete(self, object_path: str) -> None:
        path = self._path(object_path)
        if not path.exists():
            raise ObjectNotFoundError(f"object not found: {object_path}")
        path.unlink()

    def copy(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
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
        image_uri = self.copy(src_object_path, dst_object_path, overwrite)
        self.delete(src_object_path)
        return image_uri

    def make_image_uri(self, object_path: str) -> str:
        return make_file_image_uri(self.root, object_path)

    def contains_image_uri(self, image_uri: str) -> bool:
        return is_file_image_uri_under_root(self.root, image_uri)

    def validate_output_uri(self, output_uri: str) -> Path:
        return require_file_image_uri_under_root(self.root, output_uri)
