from pathlib import Path

import pandas as pd
import pytest
from pyiceberg.types import ListType, NestedField, StructType

from image_gallery.dataset_manager import (
    ColumnSpec,
    DatasetManager,
    ListFieldType,
    NameConflictError,
    StructField,
    StructFieldType,
    ValidationError,
)
from image_gallery.storage_manager import StorageManager


def nested_field_ids(field: NestedField) -> list[int]:  # pyright: ignore[reportUnknownParameterType]
    """按声明顺序收集顶层与全部嵌套 Iceberg field ID。"""
    result = [field.field_id]
    field_type = field.field_type
    if isinstance(field_type, ListType):
        result.append(field_type.element_id)
        if isinstance(field_type.element_type, StructType):
            for child in field_type.element_type.fields:
                result.extend(nested_field_ids(child))
    elif isinstance(field_type, StructType):
        for child in field_type.fields:
            result.extend(nested_field_ids(child))
    return result


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
    source_view = source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row])).view
    checkpoint = source.create_checkpoint(name="raw", source=source_view)

    cloned = repo.clone_dataset(source=checkpoint, name="Clone")

    assert cloned.open_branch().scan().to_dict(orient="records") == [row]
    assert cloned.list_checkpoints() == []
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
    base = source.schema.add_column(branch="main", base=source.open_branch(), name="split", field_type="string")

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

    fixed = source.commit(branch="main", base=base, frame=pd.DataFrame([row(b"one", "train")])).view
    source.commit(branch="main", base=fixed, frame=pd.DataFrame([row(b"two", "test")]), mode="upsert")

    cloned = repo.clone_dataset(source=fixed, name="Clone")

    assert cloned.open_branch().scan().equals(fixed.scan())
    assert {field.name for field in manager.catalog.load_table(cloned.table_identifier).schema().fields} == {
        field.name for field in manager.catalog.load_table(source.table_identifier).schema().fields
    }
    with pytest.raises(NameConflictError):
        repo.clone_dataset(source=fixed, name="clone")


def test_nested_field_ids_are_unique_stable_after_reopen_and_reallocated_for_clone(tmp_path: Path) -> None:
    storage = StorageManager()
    backend_root = tmp_path / "backend"
    manager = DatasetManager.local(root=backend_root, storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    source = repo.create_dataset(name="Source")
    nested = ColumnSpec(
        "detections",
        ListFieldType(
            StructFieldType(
                (
                    StructField("label", "string", required=True),
                    StructField(
                        "attributes",
                        StructFieldType(
                            (
                                StructField("score", "double"),
                                StructField("rank", "integer"),
                            )
                        ),
                    ),
                )
            ),
            element_required=True,
        ),
    )
    base = source.schema.add_column(branch="main", base=source.open_branch(), column=nested)
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"image")
    row = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": stored.storage_prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
        "detections": [],
    }
    fixed = source.commit(branch="main", base=base, frame=pd.DataFrame([row])).view

    source_table = manager.catalog.load_table(source.table_identifier)
    source_field = source_table.schema().find_field("detections")
    source_ids = nested_field_ids(source_field)
    assert len(source_ids) == len(set(source_ids))

    reopened = DatasetManager.local(root=backend_root, storage_manager=storage)
    reopened_source = reopened.open_repo(name="Vision").open_dataset(name="Source")
    reopened_field = reopened.catalog.load_table(reopened_source.table_identifier).schema().find_field("detections")
    assert nested_field_ids(reopened_field) == source_ids
    assert reopened_source.schema.get_column(name="detections") == nested

    reopened_fixed = reopened_source.open_branch()
    assert reopened_fixed.snapshot_id == fixed.snapshot_id
    cloned = reopened.open_repo(name="Vision").clone_dataset(source=reopened_fixed, name="Clone")
    cloned_field = reopened.catalog.load_table(cloned.table_identifier).schema().find_field("detections")
    cloned_ids = nested_field_ids(cloned_field)
    all_cloned_ids = [
        field_id
        for field in reopened.catalog.load_table(cloned.table_identifier).schema().fields
        for field_id in nested_field_ids(field)
    ]
    assert len(cloned_ids) == len(set(cloned_ids))
    assert len(all_cloned_ids) == len(set(all_cloned_ids))
    assert cloned.schema.get_column(name="detections") == nested


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
    source_view = source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row])).view

    with pytest.raises(RuntimeError, match="injected"):
        repo.clone_dataset(source=source_view, name="Clone")

    assert [dataset.name for dataset in repo.list_datasets()] == ["Source"]
    recovered = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert recovered.recover_operations() == 1
    assert recovered.open_repo(name="Vision").open_dataset(name="Clone").open_branch().scan().to_dict(
        orient="records"
    ) == [row]
