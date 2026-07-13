import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image

from image_gallery.dataset import Dataset
from image_gallery.importers import DatasetParser, ImportPipeline, LocalPathParser, UrlPathParser
from image_gallery.storage import FileSystemStorage


def test_import_pipeline_accepts_local_path_shortcut_and_writes_outputs(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGB", (4, 2), color="blue").save(source_dir / "a.jpg")
    (source_dir / "bad.jpg").write_bytes(b"not an image")

    storage = FileSystemStorage(storage_name="local_main").connect(root=tmp_path / "storage")
    pipeline = ImportPipeline(
        source=source_dir,
        storage=storage,
        output_dir=tmp_path / "outputs",
        global_tags=["dataset/project_a", "dataset/project_a", "source/customer_x"],
    )

    result = pipeline.run()

    raw_frame = Dataset.load(result.raw_dataset_path).to_frame()
    failure_frame = pd.read_json(result.failure_manifest_path, lines=True)
    managed_path = Path(raw_frame.iloc[0]["image_uri"])
    today = datetime.now().date().isoformat()

    assert raw_frame["image_uri"].str.contains(str(tmp_path / "storage"), regex=False).all()
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


def test_import_pipeline_accepts_local_path_parser_and_rolls_over_shards(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGB", (4, 2), color="blue").save(source_dir / "a.JPG")
    (source_dir / "bad.jpg").write_bytes(b"not an image")
    Image.new("RGB", (4, 2), color="green").save(source_dir / "b.png")

    storage = FileSystemStorage(storage_name="local_main").connect(root=tmp_path / "storage")
    pipeline = ImportPipeline(
        source=LocalPathParser(source_dir),
        storage=storage,
        output_dir=tmp_path / "outputs",
        max_shard_size=1,
    )

    result = pipeline.run()

    raw_frame = Dataset.load(result.raw_dataset_path).to_frame().sort_values("source_file_name")
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
        ImportPipeline(source=tmp_path, storage=storage, output_dir=tmp_path / "outputs", max_shard_size=0)


def test_import_pipeline_accepts_custom_raw_object_prefix(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGB", (4, 2), color="blue").save(source_dir / "a.jpg")
    storage = FileSystemStorage(storage_name="local_main").connect(root=tmp_path / "storage")

    result = ImportPipeline(
        source=source_dir,
        storage=storage,
        output_dir=tmp_path / "outputs",
        prefix="datasets/project_a/raw",
    ).run()

    raw_frame = Dataset.load(result.raw_dataset_path).to_frame()
    managed_path = Path(raw_frame.iloc[0]["image_uri"])
    today = datetime.now().date().isoformat()

    assert f"datasets/project_a/raw/{today}/shard_001" in managed_path.as_posix()
    assert "images/raw" not in managed_path.as_posix()


def test_import_pipeline_allows_empty_prefix(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGB", (4, 2), color="blue").save(source_dir / "a.jpg")
    storage = FileSystemStorage(storage_name="local_main").connect(root=tmp_path / "storage")

    result = ImportPipeline(source=source_dir, storage=storage, output_dir=tmp_path / "outputs", prefix="").run()

    raw_frame = Dataset.load(result.raw_dataset_path).to_frame()
    managed_path = Path(raw_frame.iloc[0]["image_uri"])
    today = datetime.now().date().isoformat()

    assert f"{today}/shard_001" in managed_path.as_posix()
    assert "images/raw" not in managed_path.as_posix()


def test_import_pipeline_accepts_dataset_parser_with_custom_image_column(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    image_path = source_dir / "a.jpg"
    Image.new("RGB", (4, 2), color="blue").save(image_path)
    dataset_path = tmp_path / "source.csv"
    pd.DataFrame([{"path": str(image_path), "origin": "original://a"}]).to_csv(dataset_path, index=False)
    storage = FileSystemStorage(storage_name="local_main").connect(root=tmp_path / "storage")

    result = ImportPipeline(
        source=DatasetParser(dataset_path, image_uri_column="path", source_uri_column="origin"),
        storage=storage,
        output_dir=tmp_path / "outputs",
    ).run()

    raw_frame = Dataset.load(result.raw_dataset_path).to_frame()
    assert raw_frame.iloc[0]["source_uri"] == "original://a"
    assert raw_frame.iloc[0]["source_type"] == "dataset"
    assert result.report == {"success_count": 1, "failure_count": 0}


def test_import_pipeline_accepts_url_path_parser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image_path = tmp_path / "fixture.jpg"
    Image.new("RGB", (4, 2), color="blue").save(image_path)
    image_bytes = image_path.read_bytes()

    class PillowResponse:
        content = image_bytes
        headers = {"content-type": "image/jpeg", "content-length": str(len(content))}

        def raise_for_status(self) -> None:
            return None

    def fake_pillow_get(url: str, timeout: int, allow_redirects: bool) -> PillowResponse:
        assert url == "https://example.com/a.jpg"
        assert timeout == 10
        assert allow_redirects is True
        return PillowResponse()

    monkeypatch.setattr("requests.get", fake_pillow_get)
    url_list = tmp_path / "urls.txt"
    url_list.write_text("https://example.com/a.jpg\n", encoding="utf-8")
    storage = FileSystemStorage(storage_name="local_main").connect(root=tmp_path / "storage")

    result = ImportPipeline(
        source=UrlPathParser(url_list, download_dir=tmp_path / "downloads"),
        storage=storage,
        output_dir=tmp_path / "outputs",
    ).run()

    raw_frame = Dataset.load(result.raw_dataset_path).to_frame()
    assert raw_frame.iloc[0]["source_uri"] == "https://example.com/a.jpg"
    assert raw_frame.iloc[0]["source_type"] == "url_path"
    assert result.report == {"success_count": 1, "failure_count": 0}


def test_import_pipeline_rejects_records_argument(tmp_path: Path) -> None:
    storage = FileSystemStorage(storage_name="local_main").connect(root=tmp_path / "storage")
    pipeline = ImportPipeline(source=tmp_path, storage=storage, output_dir=tmp_path / "outputs")

    with pytest.raises(TypeError):
        pipeline.run([])


def test_import_pipeline_rejects_invalid_source_type(tmp_path: Path) -> None:
    storage = FileSystemStorage(storage_name="local_main").connect(root=tmp_path / "storage")

    with pytest.raises(TypeError, match="source must be a SourceParser or local path"):
        ImportPipeline(source=object(), storage=storage, output_dir=tmp_path / "outputs")
