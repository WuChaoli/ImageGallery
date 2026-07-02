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
        "checksum",
        "image_format",
        "width",
        "height",
        "channels",
        "color_mode",
        "import_status",
        "imported_at",
        "schema_version",
    )
