from pathlib import Path

from image_gallery.importers import LocalDirectoryReader


def test_local_directory_reader_scans_supported_images(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"jpg")
    (tmp_path / "b.txt").write_text("not image", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "c.png").write_bytes(b"png")

    records = list(LocalDirectoryReader(tmp_path).read())

    assert [record.source_file_name for record in records] == ["a.jpg", "c.png"]
    assert records[0].source_type == "local_directory"
    assert records[0].source_uri == str(tmp_path / "a.jpg")
    assert records[1].source_relative_path == "nested/c.png"


def test_local_directory_reader_is_deterministic(tmp_path: Path) -> None:
    (tmp_path / "z.jpg").write_bytes(b"z")
    (tmp_path / "a.jpg").write_bytes(b"a")

    records = list(LocalDirectoryReader(tmp_path).read())

    assert [record.source_file_name for record in records] == ["a.jpg", "z.jpg"]
