import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
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
    managed_path = Path(raw_frame.iloc[0]["image_uri"])
    today = datetime.now().date().isoformat()

    assert raw_frame["image_uri"].str.contains(str(tmp_path / "storage")).all()
    assert managed_path.name != "a.jpg"
    assert managed_path.suffix == ".jpg"
    uuid.UUID(managed_path.stem)
    assert f"images/raw/{today}/shard_001" in managed_path.as_posix()
    assert raw_frame.iloc[0]["source_file_name"] == "a.jpg"
    assert raw_frame.iloc[0]["import_status"] == "imported"
    assert raw_frame.iloc[0]["schema_version"] == "raw.v1"
    assert list(raw_frame.iloc[0]["tags"]) == ["dataset/project_a", "source/customer_x"]
    assert result.report["success_count"] == 1
    assert result.report["failure_count"] == 1
    assert failure_frame.iloc[0]["source_uri"].endswith("bad.jpg")
    assert failure_frame.iloc[0]["error_stage"] == "metadata"


def test_import_pipeline_rolls_over_shards_by_success_count(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGB", (4, 2), color="blue").save(source_dir / "a.JPG")
    (source_dir / "bad.jpg").write_bytes(b"not an image")
    Image.new("RGB", (4, 2), color="green").save(source_dir / "b.png")

    storage = FileSystemStorage(storage_name="local_main").connect(root=tmp_path / "storage")
    pipeline = ImportPipeline(storage=storage, output_dir=tmp_path / "outputs", max_shard_size=1)

    result = pipeline.run(LocalDirectoryReader(source_dir).read())

    raw_frame = Dataset.from_path(result.raw_dataset_path).to_frame().sort_values("source_file_name")
    image_paths = [Path(image_uri) for image_uri in raw_frame["image_uri"]]
    today = datetime.now().date().isoformat()

    assert f"images/raw/{today}/shard_001" in image_paths[0].as_posix()
    assert image_paths[0].suffix == ".jpg"
    uuid.UUID(image_paths[0].stem)
    assert f"images/raw/{today}/shard_002" in image_paths[1].as_posix()
    assert image_paths[1].suffix == ".png"
    uuid.UUID(image_paths[1].stem)
    assert result.report == {"success_count": 2, "failure_count": 1}


def test_import_pipeline_rejects_invalid_max_shard_size(tmp_path: Path) -> None:
    storage = FileSystemStorage(storage_name="local_main").connect(root=tmp_path / "storage")

    with pytest.raises(ValueError, match="max_shard_size must be greater than 0"):
        ImportPipeline(storage=storage, output_dir=tmp_path / "outputs", max_shard_size=0)
