from dataclasses import dataclass
from typing import Any

from image_gallery.storage.errors import StorageNotFoundError, UnsupportedStorageTypeError
from image_gallery.storage.filesystem import FileSystemStorage
from image_gallery.storage.minio import MinioStorage


@dataclass(frozen=True)
class StorageRegistry:
    """具名 storage 的注册和连接入口。"""

    default_storage: str
    storages: dict[str, dict[str, Any]]

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "StorageRegistry":
        storages = {item["name"]: item for item in config.get("storages", [])}
        return cls(default_storage=config["default_storage"], storages=storages)

    def connect(self, storage_name: str | None = None) -> FileSystemStorage | MinioStorage:
        name = storage_name or self.default_storage
        if name not in self.storages:
            raise StorageNotFoundError(f"storage not found: {name}")

        item = self.storages[name]
        storage_type = item["type"]
        if storage_type == "filesystem":
            return FileSystemStorage(storage_name=name, root=item["root"]).connect()
        if storage_type == "minio":
            return MinioStorage(storage_name=name, config=item).connect()
        raise UnsupportedStorageTypeError(f"unsupported storage type: {storage_type}")
