from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.importers._pipeline_steps import import_record, write_import_artifacts
from image_gallery.importers.config import SourceRecord
from image_gallery.storage import FileSystemStorage


def test_import_record_boundary_preserves_uri_and_traceability(tmp_path: Path) -> None:
    image_path = tmp_path / "source.jpg"
    Image.new("RGB", (4, 2), color="blue").save(image_path)
    storage = FileSystemStorage(storage_name="local_main").connect(tmp_path / "storage")
    record = SourceRecord(
        source_uri="camera://original/source.jpg",
        source_type="local_path",
        source_file_name="source.jpg",
        source_relative_path="source.jpg",
        local_path=image_path,
    )

    result = import_record(
        record,
        storage=storage,
        global_tags=["dataset/project_a"],
        prefix="images/raw",
        import_date="2026-07-18",
        shard_index=1,
        imported_at="2026-07-18T00:00:00+00:00",
    )

    assert result.failure is None
    assert result.row is not None
    assert result.row["source_uri"] == "camera://original/source.jpg"
    assert result.row["image_uri"] != result.row["source_uri"]
    assert result.row["tags"] == ["dataset/project_a"]


def test_import_artifact_boundary_writes_failure_manifest_and_counts(tmp_path: Path) -> None:
    failure = {
        "source_uri": "file:///bad.jpg",
        "source_type": "local_path",
        "error_stage": "metadata",
        "error_code": "ValueError",
        "error_message": "bad image",
        "retryable": True,
        "occurred_at": "2026-07-18T00:00:00+00:00",
    }

    result = write_import_artifacts(tmp_path, imported_rows=[], failures=[failure])

    assert result.report == {"success_count": 0, "failure_count": 1}
    assert pd.read_json(result.failure_manifest_path, lines=True).iloc[0]["error_stage"] == "metadata"
    assert Path(result.raw_dataset_path).exists()
