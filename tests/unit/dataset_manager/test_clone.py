from pathlib import Path

import pytest

from image_gallery.dataset_manager import DatasetManager, NameConflictError, ValidationError, VectorValidationItem
from image_gallery.storage_manager import StorageManager


def test_clone_copies_fixed_state_without_history_or_vector_copy(tmp_path: Path) -> None:
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    source = repo.create_dataset(name="Source")
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"image")
    row = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": prefix.prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
    }
    source_view = source.commit(branch="main", base=source.open_branch(), rows=[row]).view
    checkpoint = source.create_checkpoint(name="raw", source=source_view)
    field = repo.create_vector_field(
        name="clip",
        dimension=2,
        distance="cosine",
        validation_set=[VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))],
    )
    field.write(source=checkpoint, items={stored.asset_id: (1.0, 2.0)}, validation_outputs=[(0.1, 0.2)])

    cloned = repo.clone_dataset(source=checkpoint, name="Clone")

    assert cloned.open_branch().scan() == [row]
    assert cloned.list_checkpoints() == []
    assert field.get(asset_id=stored.asset_id) == (1.0, 2.0)
    assert len(manager.catalog.load_table(cloned.table_identifier).snapshots()) == 1


def test_clone_rejects_view_from_another_repo(tmp_path: Path) -> None:
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    first = manager.create_repo(name="First")
    second = manager.create_repo(name="Second")
    dataset = first.create_dataset(name="Source")

    with pytest.raises(ValidationError):
        second.clone_dataset(source=dataset.open_branch(), name="Clone")


def test_clone_copies_physical_schema_and_fixed_source_state(tmp_path: Path) -> None:
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    source = repo.create_dataset(name="Source")
    base = source.add_column(branch="main", base=source.open_branch(), name="split", field_type="string")

    def row(data: bytes, split: str) -> dict[str, object]:
        stored = storage.write_managed(prefix_id=prefix.prefix_id, data=data)
        return {
            "asset_id": stored.asset_id,
            "storage_prefix_id": prefix.prefix_id,
            "relative_path": stored.relative_path,
            "source_uri": None,
            "tag_ids": [],
            "split": split,
        }

    fixed = source.commit(branch="main", base=base, rows=[row(b"one", "train")]).view
    source.commit(branch="main", base=fixed, rows=[row(b"two", "test")])

    cloned = repo.clone_dataset(source=fixed, name="Clone")

    assert cloned.open_branch().scan() == fixed.scan()
    assert {field.name for field in manager.catalog.load_table(cloned.table_identifier).schema().fields} == {
        field.name for field in manager.catalog.load_table(source.table_identifier).schema().fields
    }
    with pytest.raises(NameConflictError):
        repo.clone_dataset(source=fixed, name="clone")


def test_clone_is_hidden_and_recovered_after_candidate_interruption(tmp_path: Path) -> None:
    storage = StorageManager()

    def fail_after_candidate(_operation_id: str, phase: str) -> None:
        if phase == "clone_candidate_written":
            raise RuntimeError("injected clone interruption")

    manager = DatasetManager.local(
        root=tmp_path / "backend",
        storage_manager=storage,
        operation_hook=fail_after_candidate,
    )
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    source = repo.create_dataset(name="Source")
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"image")
    row = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": prefix.prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
    }
    source_view = source.commit(branch="main", base=source.open_branch(), rows=[row]).view

    with pytest.raises(RuntimeError, match="injected"):
        repo.clone_dataset(source=source_view, name="Clone")

    assert [dataset.name for dataset in repo.list_datasets()] == ["Source"]
    recovered = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert recovered.recover_operations() == 1
    assert recovered.open_repo(name="Vision").open_dataset(name="Clone").open_branch().scan() == [row]
