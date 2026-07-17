from dataclasses import dataclass
from pathlib import Path

import pytest
from tests.helpers.dataset_manager_importer import DatasetManagerTestImporter, DatasetManagerTestImportResult

import image_gallery
from image_gallery.dataset_manager import ConflictError, Dataset, DatasetManager, DatasetRepo
from image_gallery.importers import LocalPathParser, SourceRecord
from image_gallery.storage_manager import StorageManager, StoredObject


@dataclass(frozen=True)
class StaticParser:
    """返回测试预置来源记录。"""

    records: list[SourceRecord]

    def parse(self) -> list[SourceRecord]:
        """返回预置记录。"""
        return self.records


def make_target(tmp_path: Path) -> tuple[DatasetManager, StorageManager, DatasetRepo, Dataset, str]:
    """创建测试 Importer 使用的 local backend。"""
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "managed")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Raw")
    return manager, storage, repo, dataset, prefix.prefix_id


def test_test_importer_imports_local_parser_as_one_atomic_commit(tmp_path: Path) -> None:
    """真实目录来源应形成一次 Dataset commit。"""
    source = tmp_path / "source"
    source.mkdir()
    first = source / "first.jpg"
    second = source / "nested" / "second.png"
    second.parent.mkdir()
    first.write_bytes(b"first-image")
    second.write_bytes(b"second-image")
    manager, storage, repo, dataset, prefix_id = make_target(tmp_path)
    tag = repo.create_tag(name="imported")

    result = DatasetManagerTestImporter(
        source=LocalPathParser(source),
        dataset=dataset,
        base=dataset.open_branch(),
        storage_manager=storage,
        prefix_id=prefix_id,
        tag_ids=[tag.tag_id, tag.tag_id],
    ).run()

    assert isinstance(result, DatasetManagerTestImportResult)
    assert result.imported_count == 2
    assert len(result.asset_ids) == 2
    assert result.view.count() == 2
    rows = result.view.scan()
    assert {str(row["source_uri"]) for row in rows} == {str(first), str(second)}
    assert all(row["tag_ids"] == [tag.tag_id] for row in rows)
    assert {result.view.read_image(asset_id=asset_id) for asset_id in result.asset_ids} == {
        b"first-image",
        b"second-image",
    }
    assert result.view.snapshot_id is not None
    manager.close()
    storage.close()


def test_test_importer_rejects_record_without_local_path(tmp_path: Path) -> None:
    """测试 Importer 不应静默跳过不可读取来源。"""
    manager, storage, _, dataset, prefix_id = make_target(tmp_path)
    parser = StaticParser(
        [
            SourceRecord(
                source_uri="https://example.com/image.jpg",
                source_type="url_path",
                source_file_name="image.jpg",
                source_relative_path="image.jpg",
            )
        ]
    )

    with pytest.raises(ValueError, match="local_path"):
        DatasetManagerTestImporter(
            source=parser,
            dataset=dataset,
            base=dataset.open_branch(),
            storage_manager=storage,
            prefix_id=prefix_id,
        ).run()

    assert dataset.open_branch().count() == 0
    manager.close()
    storage.close()


def test_test_importer_rejects_stale_base_without_publishing_import(tmp_path: Path) -> None:
    """过期基线不得覆盖已经推进的 Branch。"""
    source = tmp_path / "source.jpg"
    source.write_bytes(b"source")
    manager, storage, _, dataset, prefix_id = make_target(tmp_path)
    stale = dataset.open_branch()
    existing = storage.write_managed(prefix_id=prefix_id, data=b"existing")
    dataset.commit(
        branch="main",
        base=stale,
        rows=[
            {
                "asset_id": existing.asset_id,
                "storage_prefix_id": prefix_id,
                "relative_path": existing.relative_path,
                "source_uri": None,
                "tag_ids": [],
            }
        ],
    )

    with pytest.raises(ConflictError):
        DatasetManagerTestImporter(
            source=LocalPathParser(source),
            dataset=dataset,
            base=stale,
            storage_manager=storage,
            prefix_id=prefix_id,
        ).run()

    assert dataset.open_branch().scan(columns=["asset_id"]) == [{"asset_id": existing.asset_id}]
    manager.close()
    storage.close()


def test_test_importer_storage_failure_does_not_publish_partial_dataset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """中途 Storage 失败不得发布已经准备的 Dataset 行。"""
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    manager, storage, _, dataset, prefix_id = make_target(tmp_path)
    original = storage.write_managed
    calls = 0

    def fail_second_write(*, prefix_id: str, data: bytes) -> StoredObject:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected storage failure")
        return original(prefix_id=prefix_id, data=data)

    monkeypatch.setattr(storage, "write_managed", fail_second_write)

    with pytest.raises(OSError, match="injected"):
        DatasetManagerTestImporter(
            source=LocalPathParser(tmp_path),
            dataset=dataset,
            base=dataset.open_branch(),
            storage_manager=storage,
            prefix_id=prefix_id,
        ).run()

    assert dataset.open_branch().count() == 0
    manager.close()
    storage.close()


def test_test_importer_is_not_a_production_export() -> None:
    """测试帮助类不得进入 image_gallery 公共包。"""
    assert not hasattr(image_gallery, "DatasetManagerTestImporter")
