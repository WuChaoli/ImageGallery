from pathlib import Path

import pytest

from image_gallery.importers import LocalPathParser


def test_local_path_parser_scans_supported_images_in_directory(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"jpg")
    (tmp_path / "b.txt").write_text("not image", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "c.png").write_bytes(b"png")

    records = LocalPathParser(tmp_path).parse()

    assert [record.source_file_name for record in records] == ["a.jpg", "c.png"]
    assert records[0].source_type == "local_path"
    assert records[0].source_uri == str(tmp_path / "a.jpg")
    assert records[1].source_relative_path == "nested/c.png"


def test_local_path_parser_reads_single_image_file(tmp_path: Path) -> None:
    image_path = tmp_path / "a.JPG"
    image_path.write_bytes(b"jpg")

    records = LocalPathParser(image_path).parse()

    assert len(records) == 1
    assert records[0].source_uri == str(image_path)
    assert records[0].source_file_name == "a.JPG"
    assert records[0].source_relative_path == "a.JPG"
    assert records[0].local_path == image_path


def test_local_path_parser_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "z.jpg").write_bytes(b"z")
    (tmp_path / "a.jpg").write_bytes(b"a")

    records = LocalPathParser(tmp_path).parse()

    assert [record.source_file_name for record in records] == ["a.jpg", "z.jpg"]


def test_local_path_parser_rejects_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        LocalPathParser(tmp_path / "missing").parse()


def test_local_path_parser_rejects_unsupported_file(tmp_path: Path) -> None:
    text_path = tmp_path / "a.txt"
    text_path.write_text("not image", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported image extension"):
        LocalPathParser(text_path).parse()
