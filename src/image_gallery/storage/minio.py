from dataclasses import dataclass
from typing import Any

from image_gallery.storage.base import Storage
from image_gallery.storage.errors import UnsupportedStorageTypeError


@dataclass
class MinioStorage(Storage):
    """MinIO storage 边界；依赖和集成测试在具备环境时启用。"""

    storage_name: str
    config: dict[str, Any]

    def connect(self) -> "MinioStorage":
        try:
            import minio  # noqa: F401
        except ImportError as exc:
            raise UnsupportedStorageTypeError("minio extra is not installed") from exc
        return self

    def write_bytes(self, object_path: str, data: bytes, overwrite: bool = False) -> str:
        raise NotImplementedError("MinIO write_bytes is outside the filesystem acceptance path")

    def read_bytes(self, object_path: str) -> bytes:
        raise NotImplementedError("MinIO read_bytes is outside the filesystem acceptance path")

    def exists(self, object_path: str) -> bool:
        raise NotImplementedError("MinIO exists is outside the filesystem acceptance path")

    def delete(self, object_path: str) -> None:
        raise NotImplementedError("MinIO delete is outside the filesystem acceptance path")

    def copy(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
        raise NotImplementedError("MinIO copy is outside the filesystem acceptance path")

    def move(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
        raise NotImplementedError("MinIO move is outside the filesystem acceptance path")

    def make_image_uri(self, object_path: str) -> str:
        bucket = self.config["bucket"]
        return f"s3://{bucket}/{object_path}"
