"""独立存储管理入口。"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path, PurePosixPath

from fsspec import AbstractFileSystem

from image_gallery.storage_manager._backends import (
    BackendStore,
    CredentialProvider,
    FilesystemFactory,
    OperationHook,
    create_filesystem,
)
from image_gallery.storage_manager._paths import (
    managed_relative_path,
    normalize_relative_path,
)
from image_gallery.storage_manager.errors import (
    ContentIntegrityError,
    ObjectNotFoundError,
    PathSecurityError,
    PrefixNotFoundError,
)
from image_gallery.storage_manager.models import StoragePrefix, StoredObject


class StorageManager:
    """管理 Storage Prefix 与图片 bytes IO。"""

    def __init__(
        self,
        *,
        credential_provider: CredentialProvider | None = None,
        filesystem_factory: FilesystemFactory | None = None,
        operation_hook: OperationHook | None = None,
    ) -> None:
        """创建不依赖 DatasetManager 的 StorageManager。"""
        self._prefixes: dict[str, StoragePrefix] = {}
        self._prefix_names: dict[str, str] = {}
        self._credential_provider = credential_provider
        self._filesystem_factory = filesystem_factory or create_filesystem
        self._operation_hook = operation_hook
        self._backend_store = BackendStore(
            credential_provider=lambda: self._credential_provider,
            filesystem_factory=lambda: self._filesystem_factory,
            operation_hook=lambda: self._operation_hook,
        )
        # 保留现有私有诊断入口，缓存所有权仍由 BackendStore 管理。
        self._filesystems = self._backend_store.filesystems

    def register_file_prefix(
        self,
        *,
        name: str,
        root: str | Path,
        prefix_id: str | None = None,
    ) -> StoragePrefix:
        """注册本地文件系统 Prefix。"""
        self._ensure_name_available(name)
        root_path = Path(root).resolve()
        root_path.mkdir(parents=True, exist_ok=True)
        prefix = StoragePrefix(
            prefix_id=prefix_id or str(uuid.uuid4()),
            name=name,
            backend="file",
            root=str(root_path),
        )
        self._register_prefix(prefix)
        return prefix

    def register_s3_prefix(
        self,
        *,
        name: str,
        root: str,
        endpoint_url: str,
        credential_ref: str,
        prefix_id: str | None = None,
    ) -> StoragePrefix:
        """注册只保存 secret reference 的 S3-compatible Prefix。"""
        self._ensure_name_available(name)
        normalized_root = root.strip("/")
        if not normalized_root or ".." in PurePosixPath(normalized_root).parts:
            raise PathSecurityError(root)
        prefix = StoragePrefix(
            prefix_id=prefix_id or str(uuid.uuid4()),
            name=name,
            backend="s3",
            root=normalized_root,
            credential_ref=credential_ref,
            endpoint_url=endpoint_url,
        )
        self._register_prefix(prefix)
        return prefix

    def _ensure_name_available(self, name: str) -> None:
        if name.casefold() in self._prefix_names:
            raise ValueError(f"Storage Prefix name already exists: {name}")

    def _register_prefix(self, prefix: StoragePrefix) -> None:
        if prefix.prefix_id in self._prefixes:
            raise ValueError(f"Storage Prefix ID already exists: {prefix.prefix_id}")
        self._prefixes[prefix.prefix_id] = prefix
        self._prefix_names[prefix.name.casefold()] = prefix.prefix_id

    def restore_prefix(self, prefix: StoragePrefix) -> StoragePrefix:
        """从可信控制数据库恢复冻结 Prefix 定义。"""
        existing = self._prefixes.get(prefix.prefix_id)
        if existing is not None:
            if existing != prefix:
                raise ValueError(f"Storage Prefix ID is bound to another definition: {prefix.prefix_id}")
            return existing
        self._register_prefix(prefix)
        return prefix

    def close(self) -> None:
        """关闭缓存的 Backend 客户端并释放网络资源。"""
        self._backend_store.close()

    def __enter__(self) -> StorageManager:
        """返回由上下文管理的 StorageManager。"""
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        """退出上下文时关闭缓存的 Backend 客户端。"""
        self.close()

    def get_prefix(self, *, prefix_id: str) -> StoragePrefix:
        """按稳定 ID 返回 Storage Prefix。"""
        try:
            return self._prefixes[prefix_id]
        except KeyError as exc:
            raise PrefixNotFoundError(prefix_id) from exc

    def write_bytes(
        self,
        *,
        prefix_id: str,
        relative_path: str,
        data: bytes,
        overwrite: bool = False,
    ) -> None:
        """在已注册 Prefix 内安全写入 bytes。"""
        prefix = self.get_prefix(prefix_id=prefix_id)
        normalized = self._normalize_relative_path(relative_path, allow_reserved=False)
        self._backend_store.write_bytes(
            prefix=prefix,
            relative_path=normalized,
            data=data,
            overwrite=overwrite,
        )

    def read_bytes(self, *, prefix_id: str, relative_path: str) -> bytes:
        """读取 Prefix 中的完整对象 bytes。"""
        prefix = self.get_prefix(prefix_id=prefix_id)
        normalized = self._normalize_relative_path(relative_path, allow_reserved=True)
        try:
            return self._backend_store.read_bytes(prefix=prefix, relative_path=normalized)
        except FileNotFoundError as exc:
            raise ObjectNotFoundError(relative_path) from exc

    def write_managed(self, *, prefix_id: str, data: bytes) -> StoredObject:
        """按 SHA-256 将 bytes 幂等提升为托管对象。"""
        asset_id = self._asset_id(data)
        relative_path = managed_relative_path(asset_id)
        prefix = self.get_prefix(prefix_id=prefix_id)
        self._backend_store.write_managed(
            prefix=prefix,
            relative_path=relative_path,
            asset_id=asset_id,
            data=data,
        )
        return StoredObject(asset_id=asset_id, storage_prefix_id=prefix_id, relative_path=relative_path)

    def recover_managed(self, *, prefix_id: str) -> int:
        """探测临时对象内容并幂等提升，成功后仅清理临时命名。"""
        prefix = self.get_prefix(prefix_id=prefix_id)
        return self._backend_store.recover_managed(
            prefix=prefix,
            promote=lambda data: self.write_managed(prefix_id=prefix_id, data=data),
        )

    def verify_external(
        self,
        *,
        prefix_id: str,
        relative_path: str,
        expected_asset_id: str | None = None,
    ) -> StoredObject:
        """读取外部对象并返回经真实 bytes 验证的内容身份。"""
        normalized_path = self._normalize_relative_path(relative_path, allow_reserved=False)
        data = self.read_bytes(prefix_id=prefix_id, relative_path=normalized_path)
        actual = self._asset_id(data)
        if expected_asset_id is not None and expected_asset_id != actual:
            raise ContentIntegrityError(f"expected {expected_asset_id}, got {actual}")
        return StoredObject(asset_id=actual, storage_prefix_id=prefix_id, relative_path=normalized_path)

    def verify(self, stored: StoredObject) -> bool:
        """重新读取对象并验证其内容身份。"""
        data = self.read_bytes(prefix_id=stored.storage_prefix_id, relative_path=stored.relative_path)
        actual = self._asset_id(data)
        if actual != stored.asset_id:
            raise ContentIntegrityError(f"expected {stored.asset_id}, got {actual}")
        return True

    def _filesystem(self, prefix: StoragePrefix) -> AbstractFileSystem:
        return self._backend_store.filesystem(prefix)

    @staticmethod
    def _asset_id(data: bytes) -> str:
        """分块计算规范 SHA-256 内容身份，避免额外复制大对象。"""
        digest = hashlib.sha256()
        view = memoryview(data)
        for offset in range(0, len(view), 1024 * 1024):
            digest.update(view[offset : offset + 1024 * 1024])
        return f"sha256:{digest.hexdigest()}"

    @staticmethod
    def _normalize_relative_path(relative_path: str, *, allow_reserved: bool) -> str:
        return normalize_relative_path(relative_path, allow_reserved=allow_reserved)
