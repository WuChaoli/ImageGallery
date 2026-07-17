import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from time import monotonic

import pandas as pd
import pytest
from PIL import Image
from tests.helpers.dataset_manager_importer import DatasetManagerTestImporter

from image_gallery.dataset_manager import ConflictError, DatasetManager
from image_gallery.importers import LocalPathParser
from image_gallery.model_manager import ModelDefinition, ModelManager
from image_gallery.storage_manager import StorageManager

pytestmark = pytest.mark.dataset_backend
LOGGER = logging.getLogger(__name__)


class E2ERuntime:
    """返回确定性向量的 E2E 测试模型。"""

    def embed(self, images: list[bytes]) -> list[tuple[float, ...]]:
        """为每张图片返回固定二维向量。"""
        return [(1.0, 2.0) for _ in images]

    def close(self) -> None:
        """关闭无状态测试运行时。"""


def make_model_manager() -> ModelManager:
    """创建可在数据库绑定前后复用的测试 ModelManager。"""
    return ModelManager(providers={"test": lambda _definition, _secrets: E2ERuntime()})


@contextmanager
def e2e_stage(name: str) -> Iterator[None]:
    """记录真实后端 E2E 阶段和耗时，便于定位 setup/body/teardown 阻塞。"""
    started = monotonic()
    LOGGER.info("dataset-manager-e2e stage=%s status=start", name)
    try:
        yield
    except Exception:
        LOGGER.exception("dataset-manager-e2e stage=%s status=failed", name)
        raise
    finally:
        LOGGER.info("dataset-manager-e2e stage=%s status=finished seconds=%.3f", name, monotonic() - started)


def write_image(path: Path, *, color: tuple[int, int, int]) -> bytes:
    """写入确定性合法 PNG，并返回实际 bytes。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (4, 4), color=color).save(path, format="PNG")
    return path.read_bytes()


def test_real_backend_complete_dataset_lifecycle(
    dataset_postgres_url: str,
    dataset_catalog_url: str,
    dataset_warehouse: str,
    dataset_minio_config: dict[str, str],
    tmp_path: Path,
) -> None:
    """验证从真实目录导入到重启重开的完整 Dataset 生命周期。"""
    secrets = {
        "secret://minio/tests": {
            "key": dataset_minio_config["key"],
            "secret": dataset_minio_config["secret"],
        }
    }
    file_prefix_id = "e2e-file-images"
    s3_prefix_id = "e2e-s3-images"
    file_root = tmp_path / "managed"
    source_v1 = tmp_path / "source-v1"
    first_bytes = write_image(source_v1 / "first.png", color=(255, 0, 0))
    second_bytes = write_image(source_v1 / "nested" / "second.png", color=(0, 255, 0))
    experiment_bytes = write_image(tmp_path / "experiment.png", color=(0, 0, 255))

    with e2e_stage("initial-client"):
        with StorageManager(credential_provider=lambda ref: secrets[ref]) as storage:
            models = make_model_manager()
            models.register(
                ModelDefinition(
                    model_id="clip-v1",
                    provider="test",
                    artifact_uri="memory://clip-v1",
                    artifact_revision="v1",
                    artifact_checksum="sha256:" + "1" * 64,
                    dimension=2,
                    dtype="float32",
                    config={},
                )
            )
            file_prefix = storage.register_file_prefix(
                name="file",
                root=file_root,
                prefix_id=file_prefix_id,
            )
            s3_prefix = storage.register_s3_prefix(
                name="s3",
                root=f"{dataset_minio_config['bucket']}/images",
                endpoint_url=dataset_minio_config["endpoint_url"],
                credential_ref="secret://minio/tests",
                prefix_id=s3_prefix_id,
            )
            with DatasetManager.postgres(
                control_url=dataset_postgres_url,
                catalog_url=dataset_catalog_url,
                warehouse=dataset_warehouse,
                storage_manager=storage,
                model_manager=models,
            ) as manager:
                with e2e_stage("v1-import"):
                    repo = manager.create_repo(name="Vision")
                    for prefix_id in (file_prefix.prefix_id, s3_prefix.prefix_id):
                        repo.bind_storage_prefix(prefix_id=prefix_id)
                    dataset = repo.create_dataset(name="Raw")
                    tag = repo.create_tag(name="imported")
                    imported = DatasetManagerTestImporter(
                        source=LocalPathParser(source_v1),
                        dataset=dataset,
                        base=dataset.open_branch(),
                        storage_manager=storage,
                        prefix_id=file_prefix.prefix_id,
                        tag_ids=[tag.tag_id],
                    ).run()
                    assert imported.imported_count == 2
                    assert {imported.view.read_image(asset_id=value) for value in imported.asset_ids} == {
                        first_bytes,
                        second_bytes,
                    }
                    v1_rows = imported.view.scan()
                    checkpoint = dataset.create_checkpoint(name="v1", source=imported.view)
                    dataset.create_branch(name="experiment", source=checkpoint)

                with e2e_stage("branch-and-version-evolution"):
                    field = repo.schema.add_vector(name="clip", model_id="clip-v1", distance="cosine")
                    storage.write_bytes(
                        prefix_id=s3_prefix.prefix_id,
                        relative_path="external/main-v2.png",
                        data=write_image(tmp_path / "main-v2.png", color=(255, 255, 0)),
                    )
                    main_v2_object = storage.verify_external(
                        prefix_id=s3_prefix.prefix_id,
                        relative_path="external/main-v2.png",
                    )
                    main_v2_row = {
                        "asset_id": main_v2_object.asset_id,
                        "storage_prefix_id": main_v2_object.storage_prefix_id,
                        "relative_path": main_v2_object.relative_path,
                        "source_uri": "test://main-v2",
                        "tag_ids": [tag.tag_id],
                    }
                    main_v2 = dataset.commit(
                        branch="main", base=dataset.open_branch(), frame=pd.DataFrame([main_v2_row])
                    ).view
                    generated = dataset.generate_embed(field="clip", source=main_v2)
                    assert generated.generated == 3
                    clone = repo.clone_dataset(source=main_v2, name="Clone")

                    experiment_object = storage.write_managed(
                        prefix_id=file_prefix.prefix_id,
                        data=experiment_bytes,
                    )
                    experiment_row = {
                        "asset_id": experiment_object.asset_id,
                        "storage_prefix_id": experiment_object.storage_prefix_id,
                        "relative_path": experiment_object.relative_path,
                        "source_uri": "test://experiment-v2",
                        "tag_ids": [],
                    }
                    experiment_v2 = dataset.commit(
                        branch="experiment",
                        base=dataset.open_branch(name="experiment"),
                        frame=pd.DataFrame([experiment_row]),
                    ).view

                    assert imported.view.scan().equals(v1_rows)
                    assert dataset.open_checkpoint(name="v1").scan().equals(v1_rows)
                    assert main_v2.count() == 3
                    assert experiment_v2.count() == 3
                    main_v2_rows = main_v2.scan()
                    experiment_v2_rows = experiment_v2.scan()
                    assert main_v2.get_row(asset_id=main_v2_object.asset_id).to_dict() == main_v2_row
                    assert experiment_v2.get_row(asset_id=experiment_object.asset_id).to_dict() == experiment_row
                    assert field.get(asset_id=main_v2_object.asset_id) == (1.0, 2.0)
                    with pytest.raises(ConflictError):
                        dataset.commit(branch="main", base=imported.view, frame=pd.DataFrame([]))

                with e2e_stage("rollback"):
                    rolled_back = dataset.rollback(
                        branch="main",
                        base=main_v2,
                        checkpoint=checkpoint,
                    )
                    assert rolled_back.scan().equals(v1_rows)
                    assert dataset.open_branch(name="experiment").scan().equals(experiment_v2_rows)
                    assert clone.open_branch().scan().equals(main_v2_rows)
                    assert clone.list_checkpoints() == []
                    assert field.get(asset_id=main_v2_object.asset_id) == (1.0, 2.0)

    with e2e_stage("restart-and-reopen"):
        with StorageManager(credential_provider=lambda ref: secrets[ref]) as restarted_storage:
            with DatasetManager.postgres(
                control_url=dataset_postgres_url,
                catalog_url=dataset_catalog_url,
                warehouse=dataset_warehouse,
                storage_manager=restarted_storage,
                model_manager=make_model_manager(),
            ) as restarted:
                reopened_repo = restarted.open_repo(name="vision")
                reopened_dataset = reopened_repo.open_dataset(name="raw")
                reopened_clone = reopened_repo.open_dataset(name="clone")
                reopened_field = reopened_repo.open_vector_field(name="clip")

                assert reopened_dataset.open_branch().scan().equals(v1_rows)
                assert reopened_dataset.open_checkpoint(name="v1").scan().equals(v1_rows)
                assert reopened_dataset.open_branch(name="experiment").scan().equals(experiment_v2_rows)
                assert reopened_clone.open_branch().scan().equals(main_v2_rows)
                assert reopened_clone.open_branch().read_image(asset_id=main_v2_object.asset_id) == storage_bytes(
                    restarted_storage,
                    prefix_id=s3_prefix_id,
                    relative_path="external/main-v2.png",
                )
                assert reopened_field.get(asset_id=main_v2_object.asset_id) == (1.0, 2.0)
                renamed = reopened_repo.rename_tag(tag_id=tag.tag_id, name="verified-import")
                assert renamed.tag_id == tag.tag_id
                for row in reopened_dataset.open_checkpoint(name="v1").scan().to_dict(orient="records"):
                    assert row["tag_ids"] == [tag.tag_id]


def storage_bytes(
    storage: StorageManager,
    *,
    prefix_id: str,
    relative_path: str,
) -> bytes:
    """通过重启后的 StorageManager 读取断言 bytes。"""
    return storage.read_bytes(prefix_id=prefix_id, relative_path=relative_path)
