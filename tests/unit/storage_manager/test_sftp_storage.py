"""SFTP/SSH 后端 StorageManager 单元测试。"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from image_gallery.storage_manager import (
    PathSecurityError,
    StorageManager,
    StoragePrefix,
)
from image_gallery.storage_manager._backends import create_filesystem


def test_create_filesystem_creates_sftp_with_host_and_credentials() -> None:
    """验证 SFTP 后端能通过 create_filesystem 正确构造。"""
    prefix = StoragePrefix(
        prefix_id="sftp-1",
        name="remote",
        backend="sftp",
        root="/data",
        credential_ref="secret://ssh",
        endpoint_url="192.168.1.100:22",
    )
    credentials: dict[str, object] = {"username": "test", "password": "secret"}

    with patch.object(
        __import__("fsspec.implementations.sftp", fromlist=["SFTPFileSystem"]).SFTPFileSystem,
        "_connect",
    ):
        filesystem = create_filesystem(prefix, credentials)
        assert filesystem.host == "192.168.1.100:22"
        assert filesystem.ssh_kwargs.get("username") == "test"
        assert filesystem.ssh_kwargs.get("password") == "secret"


def test_create_filesystem_handles_port_filtering_in_credentials() -> None:
    """验证 SFTP 创建时 port 从 credentials 中过滤、username 正确传递。"""
    prefix = StoragePrefix(
        prefix_id="sftp-2",
        name="remote",
        backend="sftp",
        root="/data",
        credential_ref="secret://ssh",
        endpoint_url="192.168.1.100",
    )
    credentials: dict[str, object] = {
        "username": "admin",
        "password": "pwd",
        "port": "2222",
    }

    with patch.object(
        __import__("fsspec.implementations.sftp", fromlist=["SFTPFileSystem"]).SFTPFileSystem,
        "_connect",
    ):
        filesystem = create_filesystem(prefix, credentials)
        assert filesystem.host == "192.168.1.100"
        assert "port" not in filesystem.ssh_kwargs
        assert filesystem.ssh_kwargs.get("username") == "admin"


def test_create_filesystem_fallback_to_localhost() -> None:
    """验证 endpoint_url 为空时 SFTP 默认使用 localhost。"""
    prefix = StoragePrefix(
        prefix_id="sftp-3",
        name="remote",
        backend="sftp",
        root="/data",
        credential_ref="secret://ssh",
        endpoint_url="",
    )
    credentials: dict[str, object] = {"username": "test"}

    with patch.object(
        __import__("fsspec.implementations.sftp", fromlist=["SFTPFileSystem"]).SFTPFileSystem,
        "_connect",
    ):
        filesystem = create_filesystem(prefix, credentials)
        assert filesystem.host == "localhost"


def test_create_filesystem_raises_for_unknown_backend() -> None:
    """验证未知 backend 抛出 NotImplementedError。"""
    prefix = StoragePrefix(
        prefix_id="unknown",
        name="bad",
        backend="ftp",  # type: ignore[arg-type]
        root="/data",
    )

    with pytest.raises(NotImplementedError, match="ftp"):
        create_filesystem(prefix, {})


def test_register_sftp_prefix_creates_stable_prefix() -> None:
    """验证 register_sftp_prefix 正常注册并返回正确字段。"""
    manager = StorageManager()
    prefix = manager.register_sftp_prefix(
        name="remote-images",
        root="/data/images",
        host="192.168.1.100",
        credential_ref="secret://ssh",
        prefix_id="sftp-images-v1",
    )

    assert prefix.backend == "sftp"
    assert prefix.root == "/data/images"
    assert prefix.endpoint_url == "192.168.1.100"
    assert prefix.credential_ref == "secret://ssh"

    restored = manager.get_prefix(prefix_id=prefix.prefix_id)
    assert restored == prefix


def test_register_sftp_prefix_rejects_empty_root() -> None:
    """验证空 root 被 PathSecurityError 拒绝。"""
    manager = StorageManager()

    with pytest.raises(PathSecurityError):
        manager.register_sftp_prefix(
            name="bad",
            root="",
            host="h",
            credential_ref="x",
        )


def test_register_sftp_prefix_rejects_dot_dot_in_root() -> None:
    """验证 root 中包含 .. 被拒绝。"""
    manager = StorageManager()

    with pytest.raises(PathSecurityError):
        manager.register_sftp_prefix(
            name="bad",
            root="/data/../escape",
            host="h",
            credential_ref="x",
        )


def test_register_sftp_prefix_rejects_empty_host() -> None:
    """验证空 host 被 PathSecurityError 拒绝。"""
    manager = StorageManager()

    with pytest.raises(PathSecurityError, match="host"):
        manager.register_sftp_prefix(
            name="bad",
            root="/data",
            host="",
            credential_ref="x",
        )


def test_register_sftp_preserves_root_slash() -> None:
    """验证 root=/ 时保持为 / 而非空字符串。"""
    manager = StorageManager()
    prefix = manager.register_sftp_prefix(
        name="rootfs",
        root="/",
        host="h",
        credential_ref="x",
    )

    assert prefix.root == "/"


def test_register_sftp_strips_trailing_slash() -> None:
    """验证 root 尾部 / 被去除。"""
    manager = StorageManager()
    prefix = manager.register_sftp_prefix(
        name="data",
        root="/data/images/",
        host="h",
        credential_ref="x",
    )

    assert prefix.root == "/data/images"


def test_backend_store_close_cleans_sftp_paramiko_clients() -> None:
    """验证 close() 能正确关闭 SFTP 的 ftp 和 ssh client。"""
    from image_gallery.storage_manager._backends import BackendStore

    mock_ftp = MagicMock()
    mock_ssh = MagicMock()
    mock_fs = MagicMock(spec=["ftp", "client"])
    mock_fs.ftp = mock_ftp
    mock_fs.client = mock_ssh

    store = BackendStore(
        credential_provider=lambda: None,
        filesystem_factory=lambda: create_filesystem,
        operation_hook=lambda: None,
    )
    store.filesystems["test-sftp"] = mock_fs
    store.close()

    mock_ftp.close.assert_called_once()
    mock_ssh.close.assert_called_once()
    assert store.filesystems == {}


def test_register_sftp_prefix_rejects_duplicate_name(tmp_path: Path) -> None:
    """验证重复 name（大小写不敏感）被拒绝。"""
    manager = StorageManager()
    manager.register_file_prefix(name="Images", root=tmp_path)

    with pytest.raises(ValueError, match="already exists"):
        manager.register_sftp_prefix(
            name="images",
            root="/data",
            host="h",
            credential_ref="x",
        )
