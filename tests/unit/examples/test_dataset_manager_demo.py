import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image


def test_validate_sample_manifest_accepts_twenty_unique_images(tmp_path: Path) -> None:
    from examples.dataset_manager_demo.helpers import validate_sample_manifest

    image_dir = tmp_path / "raw_images"
    image_dir.mkdir()
    items = []
    for index in range(20):
        path = image_dir / f"sample-{index:02d}.png"
        Image.new("RGB", (4, 4), (index, 0, 0)).save(path)
        data = path.read_bytes()
        items.append(
            {
                "source_image_uri": f"s3://sample/{index}.png",
                "local_path": f"raw_images/{path.name}",
                "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data),
            }
        )
    manifest = tmp_path / "sample_manifest.json"
    manifest.write_text(
        json.dumps({"seed": 20260717, "source_row_count": 1000, "sample_size": 20, "items": items}),
        encoding="utf-8",
    )

    result = validate_sample_manifest(manifest)

    assert len(result) == 20


def test_validate_sample_manifest_rejects_hash_mismatch(tmp_path: Path) -> None:
    from examples.dataset_manager_demo.helpers import validate_sample_manifest

    manifest = tmp_path / "sample_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "seed": 20260717,
                "source_row_count": 1000,
                "sample_size": 20,
                "items": [
                    {
                        "source_image_uri": f"s3://sample/{index}.png",
                        "local_path": f"raw_images/{index}.png",
                        "sha256": "0" * 64,
                        "size_bytes": 1,
                    }
                    for index in range(20)
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="不存在"):
        validate_sample_manifest(manifest)


def test_load_demo_config_reports_missing_fields_without_writing_env(tmp_path: Path) -> None:
    from examples.dataset_manager_demo.helpers import load_demo_config

    env_path = tmp_path / ".env"
    env_path.write_text("IMAGE_GALLERY_DEMO_POSTGRES_URL=postgresql://localhost/db\n", encoding="utf-8")

    probe = load_demo_config(env_path)

    assert not probe.ready
    assert "IMAGE_GALLERY_DEMO_MINIO_ENDPOINT" in probe.missing_fields
    assert env_path.read_text(encoding="utf-8").startswith("IMAGE_GALLERY_DEMO_POSTGRES_URL=")


def test_existing_session_rejects_managed_cleanup() -> None:
    from examples.dataset_manager_demo.helpers import DemoBackendSession, stop_demo_backend

    session = DemoBackendSession(mode="existing", config={})

    with pytest.raises(ValueError, match="existing"):
        stop_demo_backend(session, remove_volumes=True)


def test_select_sample_rows_is_deterministic() -> None:
    from examples.dataset_manager_demo.prepare_materials import select_sample_rows

    frame = pd.DataFrame({"image_uri": [f"s3://sample/{index}.png" for index in range(1000)]})

    first = select_sample_rows(frame)
    second = select_sample_rows(frame)

    assert len(first) == 20
    assert first["image_uri"].tolist() == second["image_uri"].tolist()
    assert len(set(first["image_uri"])) == 20


def test_probe_existing_backend_collects_service_failure(tmp_path: Path) -> None:
    from examples.dataset_manager_demo.helpers import probe_existing_backend

    env = tmp_path / ".env"
    env.write_text(
        "\n".join(
            [
                "IMAGE_GALLERY_DEMO_POSTGRES_URL=postgresql+psycopg://user:secret@db/demo",
                "IMAGE_GALLERY_DEMO_CATALOG_URL=postgresql+psycopg://user:secret@db/catalog",
                "IMAGE_GALLERY_DEMO_WAREHOUSE=file:///tmp/warehouse",
                "IMAGE_GALLERY_DEMO_MINIO_ENDPOINT=http://minio:9000",
                "IMAGE_GALLERY_DEMO_MINIO_ACCESS_KEY=access",
                "IMAGE_GALLERY_DEMO_MINIO_SECRET_KEY=secret",
                "IMAGE_GALLERY_DEMO_MINIO_BUCKET=demo",
            ]
        ),
        encoding="utf-8",
    )

    result = probe_existing_backend(env, checks=(lambda _values: None, lambda _values: "MinIO 不可连接"))

    assert not result.ready
    assert result.diagnostics == ("MinIO 不可连接",)
    assert "secret" not in " ".join(result.diagnostics)


def test_demo_importer_commits_local_images_once(tmp_path: Path) -> None:
    from examples.dataset_manager_demo.helpers import DemoDatasetImporter

    from image_gallery.dataset_manager import DatasetManager
    from image_gallery.importers import LocalPathParser
    from image_gallery.storage_manager import StorageManager

    source = tmp_path / "source"
    source.mkdir()
    for index in range(2):
        Image.new("RGB", (5, 5), (index, 0, 0)).save(source / f"{index}.png")
    storage = StorageManager()
    prefix = storage.register_file_prefix(name="demo", root=tmp_path / "objects")
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    repo = manager.create_repo(name="Demo")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Images")
    tag = repo.create_tag(name="raw")

    result = DemoDatasetImporter(
        source=LocalPathParser(source),
        dataset=dataset,
        base=dataset.open_branch(),
        storage_manager=storage,
        prefix_id=prefix.prefix_id,
        tag_ids=[tag.tag_id],
    ).run()

    assert result.imported_count == 2
    assert len(result.view.scan()) == 2
    assert all(result.view.read_image(asset_id=asset_id) for asset_id in result.asset_ids)
    manager.close()
    storage.close()


def test_dataset_manager_demo_notebook_has_chinese_lifecycle_sections() -> None:
    notebook_path = Path("examples/dataset_manager_demo/dataset_manager_demo.ipynb")
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    text = "\n".join("".join(cell["source"]) for cell in notebook["cells"])

    for heading in (
        "环境探测",
        "导入与 V1",
        "分支与版本",
        "模型托管的向量生成",
        "回退与 Clone",
        "关闭并重新连接",
        "清理",
    ):
        assert heading in text
    assert "DatasetManager.local" not in text
    assert "tests.helpers" not in text
    assert all(not cell.get("outputs") for cell in notebook["cells"] if cell["cell_type"] == "code")


def test_start_demo_backend_reports_docker_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from examples.dataset_manager_demo.helpers import start_demo_backend

    class FailingContainer:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def start(self) -> None:
            raise RuntimeError("docker unavailable")

        def with_kwargs(self, **_kwargs: object) -> "FailingContainer":
            return self

    monkeypatch.setattr("testcontainers.postgres.PostgresContainer", FailingContainer)

    with pytest.raises(RuntimeError, match="无法启动 demo Backend"):
        start_demo_backend(demo_root=tmp_path, recreate=True)


def test_managed_demo_backend_does_not_persist_credentials() -> None:
    """托管演示 Backend 不得把临时数据库或 MinIO 凭证写入磁盘。"""
    from examples.dataset_manager_demo import helpers

    source = Path(helpers.__file__).read_text(encoding="utf-8")
    assert ".env.demo" not in source
