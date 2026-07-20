from pathlib import Path

import pandas as pd
import pytest

from image_gallery.dataset_manager import (
    ColumnSpec,
    DatasetManager,
    MaterializeResult,
    NameConflictError,
    PrimitiveFieldType,
    ValidationError,
)
from image_gallery.storage_manager import StorageManager


def _setup_source(tmp_path: Path) -> tuple[StorageManager, DatasetManager, object, object, dict[str, object]]:
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    source = repo.create_dataset(name="Source")
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"image")
    row: dict[str, object] = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": stored.storage_prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
    }
    return storage, manager, repo, source, row


def test_materialize_freezes_current_schema_and_complete_frame(tmp_path: Path) -> None:
    storage, manager, repo, source, row = _setup_source(tmp_path)
    base = source.schema.add_column(branch="main", base=source.open_branch(), name="split", field_type="string")
    row["split"] = "train"
    fixed = source.commit(branch="main", base=base, frame=pd.DataFrame([row])).view
    fixed_frame = fixed.scan()
    source.schema.add_column(branch="main", base=source.open_branch(), name="score", field_type="long")

    result = repo.materialize_dataset(
        source=fixed,
        name="Clean",
        frame=fixed_frame,
        schema_additions=[ColumnSpec("quality", PrimitiveFieldType("long"))],
        checkpoint_name="initial",
    )

    assert isinstance(result, MaterializeResult)
    assert result.dataset.dataset_id != source.dataset_id
    assert result.view.dataset_id == result.dataset.dataset_id
    assert result.checkpoint is not None
    assert result.checkpoint.snapshot_id == result.view.snapshot_id
    assert result.checkpoint.ref_name == "initial"
    assert result.view.scan().to_dict(orient="records") == [{**row, "score": None, "quality": None}]
    assert [column.name for column in result.dataset.schema.list_columns()][-3:] == ["split", "score", "quality"]
    assert result.dataset.list_checkpoints() == ["initial"]
    assert (
        storage.read_bytes(prefix_id=str(row["storage_prefix_id"]), relative_path=str(row["relative_path"])) == b"image"
    )
    assert len(manager.catalog.load_table(result.dataset.table_identifier).snapshots()) == 1


def test_materialize_empty_frame_creates_first_snapshot_and_checkpoint(tmp_path: Path) -> None:
    _, _, repo, source, row = _setup_source(tmp_path)
    fixed = source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row])).view

    result = repo.materialize_dataset(
        source=fixed,
        name="Empty",
        frame=fixed.scan().iloc[0:0],
        checkpoint_name="empty",
    )

    assert result.view.snapshot_id is not None
    assert result.view.count() == 0
    assert result.checkpoint is not None
    assert result.checkpoint.snapshot_id == result.view.snapshot_id


def test_materialize_is_hidden_until_idempotent_recovery(tmp_path: Path) -> None:
    storage, manager, repo, source, row = _setup_source(tmp_path)
    fixed = source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row])).view

    def interrupt(_operation_id: str, phase: str) -> None:
        if phase == "materialize_checkpoint_created":
            raise RuntimeError("materialize interruption")

    interrupted = DatasetManager.local(
        root=tmp_path / "backend",
        storage_manager=storage,
        operation_hook=interrupt,
    )
    interrupted_repo = interrupted.open_repo(name=repo.name)
    interrupted_source = interrupted_repo.open_dataset(name=source.name).open_branch()
    with pytest.raises(RuntimeError, match="materialize interruption"):
        interrupted_repo.materialize_dataset(
            source=interrupted_source,
            name="Clean",
            frame=interrupted_source.scan(),
            checkpoint_name="initial",
        )

    assert [dataset.name for dataset in interrupted_repo.list_datasets()] == ["Source"]
    with pytest.raises(NameConflictError):
        interrupted_repo.materialize_dataset(source=interrupted_source, name="clean", frame=fixed.scan())

    recovered = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert recovered.recover_operations() == 1
    assert recovered.recover_operations() == 0
    result = recovered.open_repo(name="Vision").open_dataset(name="Clean")
    assert result.open_branch().scan().to_dict(orient="records") == [row]
    assert result.list_checkpoints() == ["initial"]


def test_materialize_rejects_invalid_source_before_catalog_side_effect(tmp_path: Path) -> None:
    _, manager, first, source, row = _setup_source(tmp_path)
    fixed = source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row])).view
    second = manager.create_repo(name="Other")

    with pytest.raises(ValidationError):
        second.materialize_dataset(source=fixed, name="Cross", frame=fixed.scan())
    with pytest.raises(ValidationError):
        first.materialize_dataset(source=source.open_branch(), name="Bad", frame=pd.DataFrame([{"asset_id": "bad"}]))

    assert not any(identifier[1].startswith("d_") for identifier in manager.catalog.list_tables(second.namespace))
