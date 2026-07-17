from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fsspec.implementations.memory import MemoryFileSystem

from image_gallery.storage_manager import (
    ContentIntegrityError,
    ObjectAlreadyExistsError,
    PathSecurityError,
    PrefixNotFoundError,
    StorageManager,
)


def test_file_prefix_reads_and_writes_bytes(tmp_path: Path) -> None:
    manager = StorageManager()
    prefix = manager.register_file_prefix(name="images", root=tmp_path)

    manager.write_bytes(prefix_id=prefix.prefix_id, relative_path="raw/a.jpg", data=b"image")

    assert manager.read_bytes(prefix_id=prefix.prefix_id, relative_path="raw/a.jpg") == b"image"


def test_prefix_names_are_unique_and_unknown_ids_are_stable_errors(tmp_path: Path) -> None:
    manager = StorageManager()
    manager.register_file_prefix(name="Images", root=tmp_path)

    with pytest.raises(ValueError, match="already exists"):
        manager.register_file_prefix(name="images", root=tmp_path / "other")
    with pytest.raises(PrefixNotFoundError):
        manager.get_prefix(prefix_id="missing")


def test_file_prefix_can_be_bootstrapped_with_stable_id_after_restart(tmp_path: Path) -> None:
    first = StorageManager()
    prefix = first.register_file_prefix(name="images", root=tmp_path, prefix_id="images-v1")
    first.write_bytes(prefix_id=prefix.prefix_id, relative_path="raw/a.jpg", data=b"image")

    restarted = StorageManager()
    restored = restarted.register_file_prefix(name="images", root=tmp_path, prefix_id=prefix.prefix_id)

    assert restored == prefix
    assert restarted.read_bytes(prefix_id="images-v1", relative_path="raw/a.jpg") == b"image"


def test_storage_manager_closes_cached_filesystems() -> None:
    filesystem = MagicMock()
    filesystem.exists.return_value = False
    manager = StorageManager(filesystem_factory=lambda _prefix, _credentials: filesystem)
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
    assert manager._filesystems == {}


def test_storage_manager_closes_s3fs_session_without_close_method() -> None:
    session = object()
    close_session = MagicMock()
    filesystem = MagicMock(spec=["close_session", "s3", "loop"])
    filesystem.close_session = close_session
    filesystem.s3 = session
    filesystem.loop = None
    manager = StorageManager()
    manager._filesystems["s3"] = filesystem

    manager.close()

    close_session.assert_called_once_with(None, session)


def test_storage_manager_does_not_double_close_finalizer_owned_s3fs_session() -> None:
    filesystem = MagicMock(spec=["close_session", "s3", "loop", "_s3creator"])
    filesystem.s3 = object()
    filesystem.loop = None
    filesystem._s3creator = object()
    manager = StorageManager()
    manager._filesystems["s3"] = filesystem

    manager.close()

    filesystem.close_session.assert_not_called()
    assert manager._filesystems == {}


def test_s3_compatible_prefix_uses_secret_reference_without_exposing_secret() -> None:
    filesystem = MemoryFileSystem(skip_instance_cache=True)
    resolved_refs: list[str] = []

    def resolve(secret_ref: str) -> dict[str, str]:
        resolved_refs.append(secret_ref)
        return {"key": "access", "secret": "do-not-render"}

    manager = StorageManager(
        credential_provider=resolve,
        filesystem_factory=lambda _prefix, _credentials: filesystem,
    )
    prefix = manager.register_s3_prefix(
        name="images",
        root="bucket/images",
        endpoint_url="http://minio:9000",
        credential_ref="secret://minio/images",
    )

    manager.write_bytes(prefix_id=prefix.prefix_id, relative_path="raw/a.jpg", data=b"image")

    assert manager.read_bytes(prefix_id=prefix.prefix_id, relative_path="raw/a.jpg") == b"image"
    assert resolved_refs == ["secret://minio/images"]
    assert "do-not-render" not in repr(prefix)

    first = manager.write_managed(prefix_id=prefix.prefix_id, data=b"managed")
    second = manager.write_managed(prefix_id=prefix.prefix_id, data=b"managed")
    assert first == second
    assert manager.verify(first) is True


def test_backslashes_are_normalized_to_posix_paths(tmp_path: Path) -> None:
    manager = StorageManager()
    prefix = manager.register_file_prefix(name="images", root=tmp_path)

    manager.write_bytes(prefix_id=prefix.prefix_id, relative_path=r"raw\a.jpg", data=b"image")

    assert manager.read_bytes(prefix_id=prefix.prefix_id, relative_path="raw/a.jpg") == b"image"


def test_file_prefix_rejects_symlink_escape(tmp_path: Path) -> None:
    manager = StorageManager()
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    outside.mkdir()
    root.mkdir()
    try:
        (root / "escape").symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation is unavailable: {exc}")
    prefix = manager.register_file_prefix(name="images", root=root)

    with pytest.raises(PathSecurityError):
        manager.write_bytes(prefix_id=prefix.prefix_id, relative_path="escape/a.jpg", data=b"image")


@pytest.mark.parametrize(
    "relative_path",
    ["../escape.jpg", "/absolute.jpg", "C:/absolute.jpg", ".image-gallery/managed/manual.jpg"],
)
def test_public_write_rejects_unsafe_or_reserved_paths(tmp_path: Path, relative_path: str) -> None:
    manager = StorageManager()
    prefix = manager.register_file_prefix(name="images", root=tmp_path)

    with pytest.raises(PathSecurityError):
        manager.write_bytes(prefix_id=prefix.prefix_id, relative_path=relative_path, data=b"image")


def test_write_does_not_overwrite_by_default(tmp_path: Path) -> None:
    manager = StorageManager()
    prefix = manager.register_file_prefix(name="images", root=tmp_path)
    manager.write_bytes(prefix_id=prefix.prefix_id, relative_path="raw/a.jpg", data=b"first")

    with pytest.raises(ObjectAlreadyExistsError):
        manager.write_bytes(prefix_id=prefix.prefix_id, relative_path="raw/a.jpg", data=b"second")


def test_managed_bytes_are_content_addressed_and_idempotent(tmp_path: Path) -> None:
    manager = StorageManager()
    prefix = manager.register_file_prefix(name="images", root=tmp_path)

    first = manager.write_managed(prefix_id=prefix.prefix_id, data=b"same-image")
    second = manager.write_managed(prefix_id=prefix.prefix_id, data=b"same-image")

    assert first == second
    assert first.asset_id.startswith("sha256:")
    assert first.relative_path.endswith(first.asset_id.removeprefix("sha256:"))
    assert manager.read_bytes(prefix_id=prefix.prefix_id, relative_path=first.relative_path) == b"same-image"


def test_managed_promote_recovers_from_temporary_write_interruption(tmp_path: Path) -> None:
    interrupted = True

    def fail_once(phase: str) -> None:
        nonlocal interrupted
        if interrupted and phase == "managed_temp_written":
            interrupted = False
            raise RuntimeError("injected promote interruption")

    manager = StorageManager(operation_hook=fail_once)
    prefix = manager.register_file_prefix(name="images", root=tmp_path)

    with pytest.raises(RuntimeError, match="promote"):
        manager.write_managed(prefix_id=prefix.prefix_id, data=b"recoverable")

    assert manager.recover_managed(prefix_id=prefix.prefix_id) == 1
    stored = manager.write_managed(prefix_id=prefix.prefix_id, data=b"recoverable")
    assert manager.verify(stored) is True
    assert manager.recover_managed(prefix_id=prefix.prefix_id) == 0


def test_external_reference_is_verified_from_real_bytes(tmp_path: Path) -> None:
    manager = StorageManager()
    prefix = manager.register_file_prefix(name="images", root=tmp_path)
    manager.write_bytes(prefix_id=prefix.prefix_id, relative_path="external/a.jpg", data=b"external")

    stored = manager.verify_external(prefix_id=prefix.prefix_id, relative_path="external/a.jpg")

    with pytest.raises(ContentIntegrityError):
        manager.verify_external(
            prefix_id=prefix.prefix_id,
            relative_path="external/a.jpg",
            expected_asset_id="sha256:" + "0" * 64,
        )
    assert manager.verify(stored) is True


def test_verify_detects_external_object_replacement(tmp_path: Path) -> None:
    manager = StorageManager()
    prefix = manager.register_file_prefix(name="images", root=tmp_path)
    manager.write_bytes(prefix_id=prefix.prefix_id, relative_path="external/a.jpg", data=b"original")
    stored = manager.verify_external(prefix_id=prefix.prefix_id, relative_path="external/a.jpg")
    manager.write_bytes(
        prefix_id=prefix.prefix_id,
        relative_path="external/a.jpg",
        data=b"changed",
        overwrite=True,
    )

    with pytest.raises(ContentIntegrityError):
        manager.verify(stored)
