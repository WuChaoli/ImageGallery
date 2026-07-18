import hashlib
from unittest.mock import MagicMock

import pytest

from image_gallery.dataset_manager._embedding import EmbeddingService
from image_gallery.dataset_manager._schema_lock import RepoSchemaLock
from image_gallery.dataset_manager._tag_store import TagStore
from image_gallery.dataset_manager._vector_store import VectorStore
from image_gallery.dataset_manager._view_io import ViewIO
from image_gallery.dataset_manager.manager import DatasetManager


def test_dataset_manager_assembles_extension_collaborators(tmp_path) -> None:  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    from image_gallery.storage_manager import StorageManager

    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=StorageManager())

    assert isinstance(manager._tags, TagStore)  # pyright: ignore[reportPrivateUsage]
    assert isinstance(manager._vectors, VectorStore)  # pyright: ignore[reportPrivateUsage]
    assert isinstance(manager._schema_lock, RepoSchemaLock)  # pyright: ignore[reportPrivateUsage]
    assert isinstance(manager._view_io, ViewIO)  # pyright: ignore[reportPrivateUsage]
    assert isinstance(manager._embedding, EmbeddingService)  # pyright: ignore[reportPrivateUsage]


def test_extension_collaborators_keep_narrow_responsibilities() -> None:
    assert {name for name in vars(TagStore) if not name.startswith("_")} == {
        "archive",
        "create",
        "rename",
        "validate_active",
    }
    assert {name for name in vars(VectorStore) if not name.startswith("_")} == {
        "create",
        "find_by_id",
        "find_by_name",
        "get_current",
        "list",
        "list_current",
        "list_existing",
        "publish_current",
    }
    assert {name for name in vars(RepoSchemaLock) if not name.startswith("_")} == {"hold"}
    assert {name for name in vars(ViewIO) if not name.startswith("_")} == {
        "get_row",
        "get_row_series",
        "read_image",
        "scan",
        "scan_frame",
        "verify_image",
    }
    assert {name for name in vars(EmbeddingService) if not name.startswith("_")} == {"generate"}


def test_postgres_schema_lock_preserves_key_and_releases_connection_on_failure() -> None:
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    connection = MagicMock()
    engine.connect.return_value = connection
    repo_id = "repo-a"
    expected_digest = hashlib.sha256(f"image-gallery-dataset-schema:{repo_id}".encode()).digest()
    expected_key = int.from_bytes(expected_digest[:8], byteorder="big", signed=True)

    with pytest.raises(RuntimeError, match="injected"):
        with RepoSchemaLock(engine).hold(repo_id=repo_id):
            raise RuntimeError("injected")

    engine.connect.assert_called_once_with()
    assert len(connection.execute.call_args_list) == 2
    lock_call, unlock_call = connection.execute.call_args_list
    assert "pg_advisory_lock" in str(lock_call.args[0])
    assert "pg_advisory_unlock" in str(unlock_call.args[0])
    assert lock_call.args[1] == {"lock_key": expected_key}
    assert unlock_call.args[1] == {"lock_key": expected_key}
    connection.close.assert_called_once_with()
