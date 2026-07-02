from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.dataset import Dataset
from image_gallery.importers import ImportPipeline, LocalDirectoryReader
from image_gallery.storage import FileSystemStorage


def test_import_pipeline_writes_raw_dataset_report_and_failures(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGB", (4, 2), color="blue").save(source_dir / "a.jpg")
    (source_dir / "bad.jpg").write_bytes(b"not an image")

    storage = FileSystemStorage(storage_name="local_main").connect(root=tmp_path / "storage")
    pipeline = ImportPipeline(
        storage=storage,
        output_dir=tmp_path / "outputs",
        global_tags=["dataset/project_a", "dataset/project_a", "source/customer_x"],
    )

    result = pipeline.run(LocalDirectoryReader(source_dir).read())

    raw_frame = Dataset.from_path(result.raw_dataset_path).to_frame()
    failure_frame = pd.read_json(result.failure_manifest_path, lines=True)

    assert raw_frame["image_uri"].str.contains(str(tmp_path / "storage")).all()
    assert raw_frame.iloc[0]["import_status"] == "imported"
    assert raw_frame.iloc[0]["schema_version"] == "raw.v1"
    assert list(raw_frame.iloc[0]["tags"]) == ["dataset/project_a", "source/customer_x"]
    assert result.report["success_count"] == 1
    assert result.report["failure_count"] == 1
    assert failure_frame.iloc[0]["source_uri"].endswith("bad.jpg")
    assert failure_frame.iloc[0]["error_stage"] == "metadata"
