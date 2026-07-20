"""StorageManager 私有 Backend IO 与 client 生命周期。"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from pathlib import PurePosixPath
from typing import BinaryIO, cast

from fsspec import AbstractFileSystem

from image_gallery.storage_manager._paths import (
    RESERVED_ROOT,
    object_path,
    resolve_file_path,
    staging_relative_path,
)
from image_gallery.storage_manager.errors import ContentIntegrityError, ObjectAlreadyExistsError, PrefixNotFoundError
from image_gallery.storage_manager.models import StoragePrefix, StoredObject

CredentialProvider = Callable[[str], Mapping[str, object]]
FilesystemFactory = Callable[[StoragePrefix, Mapping[str, object]], AbstractFileSystem]
OperationHook = Callable[[str], None]


def create_filesystem(prefix: StoragePrefix, credentials: Mapping[str, object]) -> AbstractFileSystem:
    """按 Prefix 配置创建隔离的 fsspec client。"""
    if prefix.backend == "s3":
        from s3fs import S3FileSystem

        client_kwargs = {"endpoint_url": prefix.endpoint_url} if prefix.endpoint_url else {}
        return S3FileSystem(
            key=cast(str | None, credentials.get("key")),
            secret=cast(str | None, credentials.get("secret")),
            token=cast(str | None, credentials.get("token")),
            client_kwargs=client_kwargs,
            skip_instance_cache=True,
        )
    if prefix.backend == "sftp":
        from fsspec.implementations.sftp import SFTPFileSystem

        host = prefix.endpoint_url or "localhost"
        return SFTPFileSystem(
            host=host,
            skip_instance_cache=True,
            **{k: v for k, v in credentials.items() if k != "port" and v is not None},
        )
    raise NotImplementedError(prefix.backend)


class BackendStore:
    """封装 file/S3 IO、client cache 和托管对象提升。"""

    def __init__(
        self,
        *,
        credential_provider: Callable[[], CredentialProvider | None],
        filesystem_factory: Callable[[], FilesystemFactory],
        operation_hook: Callable[[], OperationHook | None],
    ) -> None:
        """使用动态配置访问器创建 BackendStore。"""
        self._credential_provider = credential_provider
        self._filesystem_factory = filesystem_factory
        self._operation_hook = operation_hook
        self.filesystems: dict[str, AbstractFileSystem] = {}

    def filesystem(self, prefix: StoragePrefix) -> AbstractFileSystem:
        """返回 Prefix 隔离且按需创建的 fsspec client。"""
        try:
            return self.filesystems[prefix.prefix_id]
        except KeyError:
            credentials: Mapping[str, object] = {}
            if prefix.credential_ref is not None:
                provider = self._credential_provider()
                if provider is None:
                    raise PrefixNotFoundError(f"No credential provider for {prefix.prefix_id}") from None
                credentials = provider(prefix.credential_ref)
            filesystem = self._filesystem_factory()(prefix, credentials)
            self.filesystems[prefix.prefix_id] = filesystem
            return filesystem

    def close(self) -> None:
        """关闭缓存 client，并兼容 s3fs session finalizer 与 SFTP 连接。"""
        for filesystem in self.filesystems.values():
            close = getattr(filesystem, "close", None)
            if callable(close):
                close()
                continue
            close_session = getattr(filesystem, "close_session", None)
            # s3fs 已注册同步 weakref finalizer 时，手动关闭会造成二次退出 session。
            if getattr(filesystem, "_s3creator", None) is not None:
                continue
            session = getattr(filesystem, "s3", None)
            if callable(close_session) and session is not None:
                close_session(getattr(filesystem, "loop", None), session)
            # SFTPFileSystem 未实现 close，需手动关闭 paramiko 连接。
            ftp_client = getattr(filesystem, "ftp", None)
            if ftp_client is not None and hasattr(ftp_client, "close"):
                ftp_client.close()
            ssh_client = getattr(filesystem, "client", None)
            if ssh_client is not None and hasattr(ssh_client, "close"):
                ssh_client.close()
        self.filesystems.clear()

    def write_bytes(
        self,
        *,
        prefix: StoragePrefix,
        relative_path: str,
        data: bytes,
        overwrite: bool,
    ) -> None:
        """向已验证的 Backend 相对路径写入 bytes。"""
        if prefix.backend == "file":
            target = resolve_file_path(prefix=prefix, relative_path=relative_path, allow_reserved=False)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and not overwrite:
                raise ObjectAlreadyExistsError(relative_path)
            with target.open("wb" if overwrite else "xb") as stream:
                stream.write(data)
            return
        filesystem = self.filesystem(prefix)
        target = object_path(prefix=prefix, relative_path=relative_path)
        if filesystem.exists(target) and not overwrite:
            raise ObjectAlreadyExistsError(relative_path)
        with cast(BinaryIO, filesystem.open(target, "wb")) as stream:
            stream.write(data)

    def read_bytes(self, *, prefix: StoragePrefix, relative_path: str) -> bytes:
        """从已验证的 Backend 相对路径读取完整 bytes。"""
        if prefix.backend == "file":
            return resolve_file_path(prefix=prefix, relative_path=relative_path, allow_reserved=True).read_bytes()
        target = object_path(prefix=prefix, relative_path=relative_path)
        with cast(BinaryIO, self.filesystem(prefix).open(target, "rb")) as stream:
            return stream.read()

    def write_managed(
        self,
        *,
        prefix: StoragePrefix,
        relative_path: str,
        asset_id: str,
        data: bytes,
    ) -> None:
        """经 staging 将内容幂等提升到托管对象路径。"""
        if prefix.backend == "file":
            self._write_file_managed(prefix=prefix, relative_path=relative_path, asset_id=asset_id, data=data)
            return
        self._write_s3_managed(prefix=prefix, relative_path=relative_path, asset_id=asset_id, data=data)

    def recover_managed(
        self,
        *,
        prefix: StoragePrefix,
        promote: Callable[[bytes], StoredObject],
    ) -> int:
        """提升全部可恢复 staging 对象，并仅删除成功项。"""
        if prefix.backend == "file":
            temp_root = resolve_file_path(
                prefix=prefix,
                relative_path=f"{RESERVED_ROOT}/staging",
                allow_reserved=True,
            )
            temporary_objects = list(temp_root.glob("*")) if temp_root.exists() else []
            for temp in temporary_objects:
                promote(temp.read_bytes())
                temp.unlink()
            return len(temporary_objects)
        filesystem = self.filesystem(prefix)
        temp_root = object_path(prefix=prefix, relative_path=f"{RESERVED_ROOT}/staging")
        temporary_objects = list(filesystem.find(temp_root))
        for temp in temporary_objects:
            with cast(BinaryIO, filesystem.open(temp, "rb")) as stream:
                promote(stream.read())
            filesystem.rm(temp)
        return len(temporary_objects)

    def _write_file_managed(
        self,
        *,
        prefix: StoragePrefix,
        relative_path: str,
        asset_id: str,
        data: bytes,
    ) -> None:
        target = resolve_file_path(prefix=prefix, relative_path=relative_path, allow_reserved=True)
        if target.exists():
            if target.read_bytes() != data:
                raise ContentIntegrityError(asset_id)
            return
        temp = resolve_file_path(prefix=prefix, relative_path=staging_relative_path(), allow_reserved=True)
        temp.parent.mkdir(parents=True, exist_ok=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        temp.write_bytes(data)
        self._emit_operation_event("managed_temp_written")
        os.replace(temp, target)

    def _write_s3_managed(
        self,
        *,
        prefix: StoragePrefix,
        relative_path: str,
        asset_id: str,
        data: bytes,
    ) -> None:
        filesystem = self.filesystem(prefix)
        target = object_path(prefix=prefix, relative_path=relative_path)
        if filesystem.exists(target):
            with cast(BinaryIO, filesystem.open(target, "rb")) as stream:
                if stream.read() != data:
                    raise ContentIntegrityError(asset_id)
            return
        temp = object_path(prefix=prefix, relative_path=staging_relative_path())
        # 对 SFTP 等真实文件系统，需确保 staging 与 target 父目录存在；S3 makedirs 为无操作。
        filesystem.makedirs(PurePosixPath(temp).parent.as_posix(), exist_ok=True)
        filesystem.makedirs(PurePosixPath(target).parent.as_posix(), exist_ok=True)
        with cast(BinaryIO, filesystem.open(temp, "wb")) as stream:
            stream.write(data)
        self._emit_operation_event("managed_temp_written")
        filesystem.mv(temp, target)

    def _emit_operation_event(self, phase: str) -> None:
        operation_hook = self._operation_hook()
        if operation_hook is not None:
            operation_hook(phase)
