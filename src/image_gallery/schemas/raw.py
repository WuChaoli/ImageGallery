from dataclasses import dataclass


@dataclass(frozen=True)
class RawDatasetSchema:
    """导入阶段 raw Dataset 的最小字段契约。"""

    version: str = "raw.v1"
    required_columns: tuple[str, ...] = (
        "image_id",
        "source_uri",
        "source_type",
        "source_file_name",
        "storage_name",
        "image_uri",
        "file_size_bytes",
        "image_content_hash",
        "file_extension",
        "mime_type",
        "image_format",
        "width",
        "height",
        "pixel_count",
        "aspect_ratio",
        "orientation",
        "channels",
        "color_mode",
        "has_alpha",
        "animated",
        "frame_count",
        "icc_profile_present",
        "dpi_x",
        "dpi_y",
        "exif_orientation",
        "exif_datetime",
        "camera_make",
        "camera_model",
        "gps_present",
        "gps_latitude",
        "gps_longitude",
        "import_status",
        "imported_at",
        "schema_version",
        "tags",
    )
