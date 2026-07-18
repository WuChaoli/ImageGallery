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
