from pathlib import Path

import pytest

from image_gallery.storage.errors import UnsafeStoragePathError
from image_gallery.storage.uri import (
    is_file_image_uri_under_root,
    make_file_image_uri,
    require_file_image_uri_under_root,
    resolve_object_path,
)


def test_make_file_image_uri_returns_absolute_path(tmp_path: Path) -> None:
    uri = make_file_image_uri(tmp_path, "images/a.jpg")

    assert uri == str(tmp_path / "images" / "a.jpg")


def test_resolve_object_path_rejects_parent_escape(tmp_path: Path) -> None:
    with pytest.raises(UnsafeStoragePathError):
        resolve_object_path(tmp_path, "../outside.jpg")


def test_resolve_object_path_rejects_absolute_object_path(tmp_path: Path) -> None:
    with pytest.raises(UnsafeStoragePathError):
        resolve_object_path(tmp_path, "/etc/passwd")


def test_file_image_uri_belongs_to_storage_root_for_absolute_and_file_uri(tmp_path: Path) -> None:
    image_path = tmp_path / "images" / "a.jpg"

    assert is_file_image_uri_under_root(tmp_path, str(image_path)) is True
    assert is_file_image_uri_under_root(tmp_path, image_path.as_uri()) is True


def test_file_image_uri_rejects_unmanaged_path(tmp_path: Path) -> None:
    unmanaged = tmp_path.parent / "outside.jpg"

    with pytest.raises(UnsafeStoragePathError):
        require_file_image_uri_under_root(tmp_path, str(unmanaged))
