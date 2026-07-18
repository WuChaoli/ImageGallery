import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fsspec.implementations.memory import MemoryFileSystem

from image_gallery.storage_manager import StorageManager, StoragePrefix


def test_s3_managed_recovery_preserves_content_addressing() -> None:
    filesystem = MemoryFileSystem(skip_instance_cache=True)
    interrupted = True

    def fail_once(phase: str) -> None:
        nonlocal interrupted
        if interrupted and phase == "managed_temp_written":
            interrupted = False
            raise RuntimeError("injected promote interruption")

    manager = StorageManager(
        filesystem_factory=lambda _prefix, _credentials: filesystem,
        operation_hook=fail_once,
    )
    prefix = manager.register_s3_prefix(
        name="images",
        root="bucket/images",
        endpoint_url="http://minio:9000",
        credential_ref="secret://images",
    )
    manager._credential_provider = lambda _ref: {}

    with pytest.raises(RuntimeError, match="promote"):
        manager.write_managed(prefix_id=prefix.prefix_id, data=b"recoverable")

    assert manager.recover_managed(prefix_id=prefix.prefix_id) == 1
    digest = hashlib.sha256(b"recoverable").hexdigest()
    managed_path = f".image-gallery/managed/sha256/{digest[:2]}/{digest[2:4]}/{digest}"
    assert manager.read_bytes(prefix_id=prefix.prefix_id, relative_path=managed_path) == b"recoverable"
    stored = manager.write_managed(prefix_id=prefix.prefix_id, data=b"recoverable")
    assert manager.verify(stored) is True
    assert manager.recover_managed(prefix_id=prefix.prefix_id) == 0


def test_restore_prefix_rejects_definition_drift(tmp_path: Path) -> None:
    manager = StorageManager()
    prefix = manager.register_file_prefix(name="images", root=tmp_path, prefix_id="images-v1")

    with pytest.raises(ValueError, match="bound to another definition"):
        manager.restore_prefix(
            StoragePrefix(
                prefix_id=prefix.prefix_id,
                name=prefix.name,
                backend="file",
                root=str(tmp_path / "other"),
            )
        )


def test_context_exit_closes_each_cached_filesystem_once() -> None:
    filesystem = MagicMock()
    filesystem.exists.return_value = False

    with StorageManager(filesystem_factory=lambda _prefix, _credentials: filesystem) as manager:
        prefix = manager.register_s3_prefix(
            name="images",
            root="bucket/images",
            endpoint_url="http://minio:9000",
            credential_ref="secret://images",
        )
        manager._credential_provider = lambda _ref: {}
        manager._filesystem(prefix)

    manager.close()

    filesystem.close.assert_called_once_with()
