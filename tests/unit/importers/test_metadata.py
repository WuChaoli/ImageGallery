from pathlib import Path

from PIL import Image

from image_gallery.importers.metadata import extract_basic_metadata


def test_extract_basic_metadata_reads_image_facts(tmp_path: Path) -> None:
    image_path = tmp_path / "a.jpg"
    Image.new("RGB", (16, 8), color="red").save(image_path)

    metadata = extract_basic_metadata(image_path)

    assert metadata["file_size_bytes"] > 0
    assert metadata["checksum"].startswith("sha256:")
    assert metadata["image_format"] == "JPEG"
    assert metadata["width"] == 16
    assert metadata["height"] == 8
    assert metadata["channels"] == 3
    assert metadata["color_mode"] == "RGB"
