import json
import uuid
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset
from image_gallery.importers.config import SourceRecord
from image_gallery.importers.metadata import extract_basic_metadata
from image_gallery.importers.report import ImportResult
from image_gallery.schemas import RawDatasetSchema, validate_raw_dataset
from image_gallery.storage import Storage


@dataclass(frozen=True)
class _RecordImportResult:
    """单条来源导入的成功行或失败记录。"""

    row: dict[str, object] | None = None
    failure: dict[str, object] | None = None


def import_record(
    record: SourceRecord,
    *,
    storage: Storage,
    global_tags: list[str],
    prefix: str,
    import_date: str,
    shard_index: int,
    imported_at: str,
) -> _RecordImportResult:
    """导入单条来源，并把任意单项异常转换为失败记录。"""
    error_stage = "source"
    try:
        if record.local_path is None:
            raise ValueError("local_path is required for current import mode")
        error_stage = "metadata"
        metadata = extract_basic_metadata(record.local_path)
        image_id = str(uuid.uuid4())
        object_path = build_raw_object_path(
            prefix,
            import_date,
            shard_index,
            image_id,
            record.source_file_name,
        )
        error_stage = "storage"
        image_uri = storage.write_bytes(object_path, record.local_path.read_bytes(), overwrite=False)
        return _RecordImportResult(
            row={
                "image_id": image_id,
                "source_uri": record.source_uri,
                "source_type": record.source_type,
                "source_file_name": record.source_file_name,
                "storage_name": storage.storage_name,
                "image_uri": image_uri,
                "import_status": "imported",
                "imported_at": imported_at,
                "schema_version": RawDatasetSchema.version,
                "tags": global_tags,
                **metadata,
            }
        )
    # 导入流水线必须将单个来源失败写入结构化 failures。
    except Exception as exc:  # noqa: BLE001
        return _RecordImportResult(
            failure={
                "source_uri": record.source_uri,
                "source_type": record.source_type,
                "error_stage": error_stage,
                "error_code": exc.__class__.__name__,
                "error_message": str(exc),
                "retryable": True,
                "occurred_at": imported_at,
            }
        )


def write_import_artifacts(
    output_dir: Path,
    *,
    imported_rows: list[dict[str, object]],
    failures: list[dict[str, object]],
) -> ImportResult:
    """写出 raw Dataset、失败清单和导入报告。"""
    raw_dataset_path = str(output_dir / "raw.parquet")
    failure_manifest_path = str(output_dir / "failure_manifest.jsonl")
    import_report_path = str(output_dir / "import_report.json")

    raw_frame = pd.DataFrame(imported_rows)
    if not raw_frame.empty:
        validate_raw_dataset(raw_frame)
    Dataset.write(raw_frame, raw_dataset_path)

    pd.DataFrame(failures).to_json(failure_manifest_path, orient="records", lines=True, force_ascii=False)
    report = {"success_count": len(imported_rows), "failure_count": len(failures)}
    Path(import_report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return ImportResult(
        raw_dataset_path=raw_dataset_path,
        import_report_path=import_report_path,
        failure_manifest_path=failure_manifest_path,
        report=report,
    )


def build_raw_object_path(
    prefix: str,
    import_date: str,
    shard_index: int,
    image_id: str,
    source_file_name: str,
) -> str:
    """生成 raw 图片在受管 storage 中的日期分片路径。"""
    extension = Path(source_file_name).suffix.lower()
    object_name = f"{import_date}/shard_{shard_index:03d}/{image_id}{extension}"
    if not prefix:
        return object_name
    return f"{prefix}/{object_name}"
