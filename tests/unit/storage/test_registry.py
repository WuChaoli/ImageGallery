from pathlib import Path

import pytest

from image_gallery.storage import FileSystemStorage, StorageRegistry
from image_gallery.storage.errors import StorageNotFoundError, UnsupportedStorageTypeError


def test_registry_connects_default_filesystem_storage(tmp_path: Path) -> None:
    registry = StorageRegistry.from_config(
        {
            "default_storage": "local_main",
            "storages": [
                {"name": "local_main", "type": "filesystem", "root": str(tmp_path)},
            ],
        }
    )

    storage = registry.connect()

    assert isinstance(storage, FileSystemStorage)
    assert storage.storage_name == "local_main"


def test_registry_rejects_missing_storage(tmp_path: Path) -> None:
    registry = StorageRegistry.from_config(
        {
            "default_storage": "local_main",
            "storages": [
                {"name": "local_main", "type": "filesystem", "root": str(tmp_path)},
            ],
        }
    )

    with pytest.raises(StorageNotFoundError):
        registry.connect("missing")


def test_registry_rejects_unsupported_storage_type() -> None:
    registry = StorageRegistry.from_config(
        {
            "default_storage": "remote",
            "storages": [
                {"name": "remote", "type": "unknown", "root": "/tmp/storage"},
            ],
        }
    )

    with pytest.raises(UnsupportedStorageTypeError):
        registry.connect("remote")
