import json
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset
from image_gallery.importers.config import SourceRecord
from image_gallery.importers.metadata import extract_basic_metadata
from image_gallery.importers.report import ImportResult
from image_gallery.schemas import RawDatasetSchema, validate_raw_dataset
from image_gallery.storage import Storage


class ImportPipeline:
    """把 SourceRecord 转换为受管 storage 中的 raw Dataset。"""

    def __init__(
        self,
        storage: Storage,
        output_dir: str | Path,
        global_tags: Iterable[str] | None = None,
    ) -> None:
        self.storage = storage
        self.output_dir = Path(output_dir)
        self.global_tags = _unique_tags(global_tags or [])

    def run(self, records: Iterable[SourceRecord]) -> ImportResult:
        """执行 copy 模式导入，并写出 raw Dataset、报告和失败清单。"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        imported_rows: list[dict[str, object]] = []
        failures: list[dict[str, object]] = []

        for record in records:
            imported_at = datetime.now(timezone.utc).isoformat()
            error_stage = "source"
            try:
                if record.local_path is None:
                    raise ValueError("local_path is required for current import mode")
                error_stage = "metadata"
                metadata = extract_basic_metadata(record.local_path)
                image_id = str(uuid.uuid4())
                object_path = f"images/raw/{image_id}/{record.source_file_name}"
                error_stage = "storage"
                image_uri = self.storage.write_bytes(object_path, record.local_path.read_bytes(), overwrite=False)
                imported_rows.append(
                    {
                        "image_id": image_id,
                        "source_uri": record.source_uri,
                        "source_type": record.source_type,
                        "source_file_name": record.source_file_name,
                        "storage_name": self.storage.storage_name,
                        "image_uri": image_uri,
                        "import_status": "imported",
                        "imported_at": imported_at,
                        "schema_version": RawDatasetSchema.version,
                        "tags": self.global_tags,
                        **metadata,
                    }
                )
            except Exception as exc:
                failures.append(
                    {
                        "source_uri": record.source_uri,
                        "source_type": record.source_type,
                        "error_stage": error_stage,
                        "error_code": exc.__class__.__name__,
                        "error_message": str(exc),
                        "retryable": True,
                        "occurred_at": imported_at,
                    }
                )

        raw_dataset_path = str(self.output_dir / "raw.parquet")
        failure_manifest_path = str(self.output_dir / "failure_manifest.jsonl")
        import_report_path = str(self.output_dir / "import_report.json")

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


def _unique_tags(tags: Iterable[str]) -> list[str]:
    """按输入顺序去重 global_tags。"""
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result
