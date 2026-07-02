from pathlib import Path

import pytest

from image_gallery.storage import FileSystemStorage
from image_gallery.storage.errors import ObjectAlreadyExistsError, ObjectNotFoundError, UnsafeStoragePathError


def test_filesystem_storage_writes_and_reads_bytes(tmp_path: Path) -> None:
    storage = FileSystemStorage(storage_name="local_main", root=tmp_path).connect()

    image_uri = storage.write_bytes("images/a.jpg", b"abc")

    assert image_uri == str(tmp_path / "images" / "a.jpg")
    assert storage.read_bytes("images/a.jpg") == b"abc"
    assert storage.exists("images/a.jpg") is True


def test_filesystem_storage_does_not_overwrite_by_default(tmp_path: Path) -> None:
    storage = FileSystemStorage(storage_name="local_main", root=tmp_path).connect()
    storage.write_bytes("images/a.jpg", b"abc")

    with pytest.raises(ObjectAlreadyExistsError):
        storage.write_bytes("images/a.jpg", b"def")


def test_filesystem_storage_copy_move_delete(tmp_path: Path) -> None:
    storage = FileSystemStorage(storage_name="local_main", root=tmp_path).connect()
    storage.write_bytes("images/a.jpg", b"abc")

    copy_uri = storage.copy("images/a.jpg", "images/b.jpg")
    move_uri = storage.move("images/b.jpg", "images/c.jpg")
    storage.delete("images/a.jpg")

    assert copy_uri == str(tmp_path / "images" / "b.jpg")
    assert move_uri == str(tmp_path / "images" / "c.jpg")
    assert storage.exists("images/a.jpg") is False
    assert storage.read_bytes("images/c.jpg") == b"abc"


def test_filesystem_storage_rejects_path_escape(tmp_path: Path) -> None:
    storage = FileSystemStorage(storage_name="local_main", root=tmp_path).connect()

    with pytest.raises(UnsafeStoragePathError):
        storage.write_bytes("../outside.jpg", b"abc")


def test_filesystem_storage_raises_for_missing_object(tmp_path: Path) -> None:
    storage = FileSystemStorage(storage_name="local_main", root=tmp_path).connect()

    with pytest.raises(ObjectNotFoundError):
        storage.read_bytes("missing.jpg")


def test_filesystem_storage_validates_managed_output_path(tmp_path: Path) -> None:
    storage = FileSystemStorage(storage_name="local_main", root=tmp_path).connect()
    managed = tmp_path / "datasets" / "raw.parquet"
    unmanaged = tmp_path.parent / "raw.parquet"

    assert storage.validate_output_path(str(managed)) == managed
    assert storage.contains_image_uri(managed.as_uri()) is True

    with pytest.raises(UnsafeStoragePathError):
        storage.validate_output_path(str(unmanaged))
