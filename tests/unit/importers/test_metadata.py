from pathlib import Path

from PIL import Image

from image_gallery.importers.metadata import extract_basic_metadata


def test_extract_basic_metadata_reads_image_facts(tmp_path: Path) -> None:
    image_path = tmp_path / "a.jpg"
    Image.new("RGB", (16, 8), color="red").save(image_path, dpi=(72, 96))

    metadata = extract_basic_metadata(image_path)

    assert metadata["file_size_bytes"] > 0
    assert metadata["image_content_hash"].startswith("sha256:")
    assert metadata["file_extension"] == ".jpg"
    assert metadata["mime_type"] == "image/jpeg"
    assert metadata["image_format"] == "JPEG"
    assert metadata["width"] == 16
    assert metadata["height"] == 8
    assert metadata["pixel_count"] == 128
    assert metadata["aspect_ratio"] == 2.0
    assert metadata["orientation"] == "landscape"
    assert metadata["channels"] == 3
    assert metadata["color_mode"] == "RGB"
    assert metadata["has_alpha"] is False
    assert metadata["animated"] is False
    assert metadata["frame_count"] == 1
    assert metadata["icc_profile_present"] is False
    assert metadata["dpi_x"] == 72
    assert metadata["dpi_y"] == 96
    assert metadata["exif_orientation"] is None
    assert metadata["exif_datetime"] is None
    assert metadata["camera_make"] is None
    assert metadata["camera_model"] is None
    assert metadata["gps_present"] is False
    assert metadata["gps_latitude"] is None
    assert metadata["gps_longitude"] is None


def test_extract_basic_metadata_detects_alpha_and_square_orientation(tmp_path: Path) -> None:
    image_path = tmp_path / "alpha.PNG"
    Image.new("RGBA", (8, 8), color=(255, 0, 0, 128)).save(image_path)

    metadata = extract_basic_metadata(image_path)

    assert metadata["file_extension"] == ".png"
    assert metadata["mime_type"] == "image/png"
    assert metadata["orientation"] == "square"
    assert metadata["channels"] == 4
    assert metadata["color_mode"] == "RGBA"
    assert metadata["has_alpha"] is True
