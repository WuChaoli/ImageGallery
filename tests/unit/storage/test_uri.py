from pathlib import Path

import pytest

from image_gallery.storage.errors import UnsafeStoragePathError
from image_gallery.storage.uri import make_file_image_uri, resolve_object_path


def test_make_file_image_uri_returns_absolute_path(tmp_path: Path) -> None:
    uri = make_file_image_uri(tmp_path, "images/a.jpg")

    assert uri == str(tmp_path / "images" / "a.jpg")


def test_resolve_object_path_rejects_parent_escape(tmp_path: Path) -> None:
    with pytest.raises(UnsafeStoragePathError):
        resolve_object_path(tmp_path, "../outside.jpg")


def test_resolve_object_path_rejects_absolute_object_path(tmp_path: Path) -> None:
    with pytest.raises(UnsafeStoragePathError):
        resolve_object_path(tmp_path, "/etc/passwd")
