"""独立存储管理入口。"""

from __future__ import annotations

import hashlib
import os
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import BinaryIO, cast

from fsspec import AbstractFileSystem

from image_gallery.storage_manager.errors import (
    ContentIntegrityError,
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    PathSecurityError,
    PrefixNotFoundError,
)
from image_gallery.storage_manager.models import StoragePrefix, StoredObject

_RESERVED_ROOT = ".image-gallery"
CredentialProvider = Callable[[str], Mapping[str, object]]
FilesystemFactory = Callable[[StoragePrefix, Mapping[str, object]], AbstractFileSystem]
OperationHook = Callable[[str], None]


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
        self._filesystem_factory = filesystem_factory or self._create_filesystem
        self._operation_hook = operation_hook
        self._filesystems: dict[str, AbstractFileSystem] = {}

    def register_file_prefix(
        self,
        *,
        name: str,
        root: str | Path,
        prefix_id: str | None = None,
    ) -> StoragePrefix:
        """注册本地文件系统 Prefix。"""
        normalized_name = name.casefold()
        if normalized_name in self._prefix_names:
            raise ValueError(f"Storage Prefix name already exists: {name}")
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
        normalized_name = name.casefold()
        if normalized_name in self._prefix_names:
            raise ValueError(f"Storage Prefix name already exists: {name}")
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
        for filesystem in self._filesystems.values():
            close = getattr(filesystem, "close", None)
            if callable(close):
                close()
                continue
            close_session = getattr(filesystem, "close_session", None)
            # s3fs 已为 _s3creator 注册同步 weakref finalizer；手动关闭 client 会导致 finalizer 二次退出 session。
            if getattr(filesystem, "_s3creator", None) is not None:
                continue
            session = getattr(filesystem, "s3", None)
            if callable(close_session) and session is not None:
                close_session(getattr(filesystem, "loop", None), session)
        self._filesystems.clear()

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
        if prefix.backend == "file":
            target = self._resolve_file_path(prefix_id=prefix_id, relative_path=normalized, allow_reserved=False)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and not overwrite:
                raise ObjectAlreadyExistsError(relative_path)
            mode = "wb" if overwrite else "xb"
            with target.open(mode) as stream:
                stream.write(data)
            return
        filesystem = self._filesystem(prefix)
        target = self._object_path(prefix=prefix, relative_path=normalized)
        if filesystem.exists(target) and not overwrite:
            raise ObjectAlreadyExistsError(relative_path)
        with cast(BinaryIO, filesystem.open(target, "wb")) as stream:
            stream.write(data)

    def read_bytes(self, *, prefix_id: str, relative_path: str) -> bytes:
        """读取 Prefix 中的完整对象 bytes。"""
        prefix = self.get_prefix(prefix_id=prefix_id)
        normalized = self._normalize_relative_path(relative_path, allow_reserved=True)
        try:
            if prefix.backend == "file":
                target = self._resolve_file_path(prefix_id=prefix_id, relative_path=normalized, allow_reserved=True)
                return target.read_bytes()
            object_path = self._object_path(prefix=prefix, relative_path=normalized)
            with cast(BinaryIO, self._filesystem(prefix).open(object_path, "rb")) as stream:
                return stream.read()
        except FileNotFoundError as exc:
            raise ObjectNotFoundError(relative_path) from exc

    def write_managed(self, *, prefix_id: str, data: bytes) -> StoredObject:
        """按 SHA-256 将 bytes 幂等提升为托管对象。"""
        asset_id = self._asset_id(data)
        digest = asset_id.removeprefix("sha256:")
        relative_path = f"{_RESERVED_ROOT}/managed/sha256/{digest[:2]}/{digest[2:4]}/{digest}"
        prefix = self.get_prefix(prefix_id=prefix_id)
        if prefix.backend == "s3":
            filesystem = self._filesystem(prefix)
            target = self._object_path(prefix=prefix, relative_path=relative_path)
            if filesystem.exists(target):
                with cast(BinaryIO, filesystem.open(target, "rb")) as stream:
                    existing = stream.read()
                if existing != data:
                    raise ContentIntegrityError(asset_id)
            else:
                temp_relative = f"{_RESERVED_ROOT}/staging/{uuid.uuid4().hex}"
                temp = self._object_path(prefix=prefix, relative_path=temp_relative)
                with cast(BinaryIO, filesystem.open(temp, "wb")) as stream:
                    stream.write(data)
                self._emit_operation_event("managed_temp_written")
                filesystem.mv(temp, target)
            return StoredObject(asset_id=asset_id, storage_prefix_id=prefix_id, relative_path=relative_path)
        target = self._resolve_file_path(prefix_id=prefix_id, relative_path=relative_path, allow_reserved=True)
        if target.exists():
            existing = target.read_bytes()
            if existing != data:
                raise ContentIntegrityError(asset_id)
        else:
            temp_relative = f"{_RESERVED_ROOT}/staging/{uuid.uuid4().hex}"
            temp = self._resolve_file_path(prefix_id=prefix_id, relative_path=temp_relative, allow_reserved=True)
            temp.parent.mkdir(parents=True, exist_ok=True)
            target.parent.mkdir(parents=True, exist_ok=True)
            temp.write_bytes(data)
            self._emit_operation_event("managed_temp_written")
            os.replace(temp, target)
        return StoredObject(asset_id=asset_id, storage_prefix_id=prefix_id, relative_path=relative_path)

    def recover_managed(self, *, prefix_id: str) -> int:
        """探测临时对象内容并幂等提升，成功后仅清理临时命名。"""
        prefix = self.get_prefix(prefix_id=prefix_id)
        recovered = 0
        if prefix.backend == "file":
            temp_root = Path(prefix.root) / _RESERVED_ROOT / "staging"
            for temp in temp_root.glob("*") if temp_root.exists() else []:
                self.write_managed(prefix_id=prefix_id, data=temp.read_bytes())
                temp.unlink()
                recovered += 1
            return recovered
        filesystem = self._filesystem(prefix)
        temp_root = self._object_path(prefix=prefix, relative_path=f"{_RESERVED_ROOT}/staging")
        for temp in filesystem.find(temp_root):
            with cast(BinaryIO, filesystem.open(temp, "rb")) as stream:
                self.write_managed(prefix_id=prefix_id, data=stream.read())
            filesystem.rm(temp)
            recovered += 1
        return recovered

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

    def _resolve_file_path(self, *, prefix_id: str, relative_path: str, allow_reserved: bool) -> Path:
        prefix = self.get_prefix(prefix_id=prefix_id)
        if prefix.backend != "file":
            raise NotImplementedError(f"Backend is not implemented: {prefix.backend}")
        normalized = self._normalize_relative_path(relative_path, allow_reserved=allow_reserved)
        root = Path(prefix.root).resolve()
        candidate = root.joinpath(*PurePosixPath(normalized).parts)
        resolved = candidate.resolve(strict=False)
        if resolved != root and root not in resolved.parents:
            raise PathSecurityError(relative_path)
        return resolved

    def _filesystem(self, prefix: StoragePrefix) -> AbstractFileSystem:
        try:
            return self._filesystems[prefix.prefix_id]
        except KeyError:
            credentials: Mapping[str, object] = {}
            if prefix.credential_ref is not None:
                if self._credential_provider is None:
                    raise PrefixNotFoundError(f"No credential provider for {prefix.prefix_id}") from None
                credentials = self._credential_provider(prefix.credential_ref)
            filesystem = self._filesystem_factory(prefix, credentials)
            self._filesystems[prefix.prefix_id] = filesystem
            return filesystem

    @staticmethod
    def _create_filesystem(prefix: StoragePrefix, credentials: Mapping[str, object]) -> AbstractFileSystem:
        """按 Prefix 配置创建隔离的 fsspec client。"""
        if prefix.backend != "s3":
            raise NotImplementedError(prefix.backend)
        from s3fs import S3FileSystem

        client_kwargs = {"endpoint_url": prefix.endpoint_url} if prefix.endpoint_url else {}
        key = credentials.get("key")
        secret = credentials.get("secret")
        token = credentials.get("token")
        return S3FileSystem(
            key=cast(str | None, key),
            secret=cast(str | None, secret),
            token=cast(str | None, token),
            client_kwargs=client_kwargs,
            skip_instance_cache=True,
        )

    @staticmethod
    def _object_path(*, prefix: StoragePrefix, relative_path: str) -> str:
        return f"{prefix.root.rstrip('/')}/{relative_path}"

    @staticmethod
    def _asset_id(data: bytes) -> str:
        """分块计算规范 SHA-256 内容身份，避免额外复制大对象。"""
        digest = hashlib.sha256()
        view = memoryview(data)
        for offset in range(0, len(view), 1024 * 1024):
            digest.update(view[offset : offset + 1024 * 1024])
        return f"sha256:{digest.hexdigest()}"

    def _emit_operation_event(self, phase: str) -> None:
        if self._operation_hook is not None:
            self._operation_hook(phase)

    @staticmethod
    def _normalize_relative_path(relative_path: str, *, allow_reserved: bool) -> str:
        normalized = relative_path.replace("\\", "/")
        path = PurePosixPath(normalized)
        if not normalized or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
            raise PathSecurityError(relative_path)
        if not allow_reserved and path.parts[0] == _RESERVED_ROOT:
            raise PathSecurityError(relative_path)
        return path.as_posix()
