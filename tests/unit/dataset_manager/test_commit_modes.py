from pathlib import Path
from typing import cast

import pandas as pd
import pytest

from image_gallery.dataset_manager import (
    ColumnSpec,
    ConflictError,
    Dataset,
    DatasetManager,
    NameConflictError,
    PrimitiveFieldType,
    ValidationError,
)
from image_gallery.model_manager import ModelDefinition
from image_gallery.storage_manager import StorageManager


def _dataset(tmp_path: Path):
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    return storage, prefix, repo.create_dataset(name="Raw")


def _row(storage: StorageManager, prefix_id: str, data: bytes, **extra: object) -> dict[str, object]:
    stored = storage.write_managed(prefix_id=prefix_id, data=data)
    return {
        "asset_id": stored.asset_id,
        "storage_prefix_id": stored.storage_prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
        **extra,
    }


def test_replace_is_default_and_reports_removed_rows(tmp_path: Path) -> None:
    storage, prefix, dataset = _dataset(tmp_path)
    first = _row(storage, prefix.prefix_id, b"one")
    second = _row(storage, prefix.prefix_id, b"two")
    base = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([first, second])).view

    result = dataset.commit(branch="main", base=base, frame=pd.DataFrame([first]))

    assert result.inserted == 0
    assert result.updated == 0
    assert result.removed == 1
    assert result.view.scan().to_dict(orient="records") == [first]


def test_upsert_and_patch_are_explicit_and_counts_are_precise(tmp_path: Path) -> None:
    storage, prefix, dataset = _dataset(tmp_path)
    dataset.schema.add_column(
        branch="main",
        base=dataset.open_branch(),
        column=ColumnSpec("score", PrimitiveFieldType("long")),
    )
    first = _row(storage, prefix.prefix_id, b"one", score=1)
    second = _row(storage, prefix.prefix_id, b"two", score=2)
    base = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([first])).view
    upsert = dataset.commit(branch="main", base=base, frame=pd.DataFrame([second]), mode="upsert")
    patch = dataset.commit(
        branch="main",
        base=upsert.view,
        frame=pd.DataFrame([{"asset_id": first["asset_id"], "score": 3}]),
        mode="patch",
        fields=["score"],
    )

    assert (upsert.inserted, upsert.updated, upsert.removed) == (1, 0, 0)
    assert (patch.inserted, patch.updated, patch.removed) == (0, 1, 0)
    assert dict(zip(patch.view.scan()["asset_id"], patch.view.scan()["score"], strict=True)) == {
        first["asset_id"]: 3,
        second["asset_id"]: 2,
    }
    with pytest.raises(ValidationError):
        dataset.commit(branch="main", base=patch.view, frame=pd.DataFrame([second]), mode="patch")


def test_commit_can_add_schema_and_checkpoint_atomically(tmp_path: Path) -> None:
    storage, prefix, dataset = _dataset(tmp_path)
    row = _row(storage, prefix.prefix_id, b"one", score=1)

    result = dataset.commit(
        branch="main",
        base=dataset.open_branch(),
        frame=pd.DataFrame([row]),
        schema_additions=[ColumnSpec("score", PrimitiveFieldType("long"))],
        checkpoint_name="clean-v1",
    )

    assert result.changed is True
    assert result.checkpoint is not None
    assert result.checkpoint.snapshot_id == result.view.snapshot_id
    assert dataset.open_checkpoint(name="clean-v1").scan().to_dict(orient="records") == [row]


def test_schema_only_commit_changes_schema_without_row_counts(tmp_path: Path) -> None:
    storage, prefix, dataset = _dataset(tmp_path)
    row = _row(storage, prefix.prefix_id, b"one")
    base = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row])).view

    result = dataset.commit(
        branch="main",
        base=base,
        frame=pd.DataFrame([row]),
        schema_additions=[ColumnSpec("score", PrimitiveFieldType("long"))],
    )

    assert (result.inserted, result.updated, result.removed) == (0, 0, 0)
    assert result.changed is True
    assert result.view.scan().iloc[0]["score"] is None


def test_empty_replace_can_create_snapshot_anchor_for_checkpoint(tmp_path: Path) -> None:
    _, _, dataset = _dataset(tmp_path)
    columns = [column.name for column in dataset.schema.list_columns()]

    result = dataset.commit(
        branch="main",
        base=dataset.open_branch(),
        frame=pd.DataFrame(columns=columns),
        checkpoint_name="empty-v1",
    )

    assert result.changed is False
    assert result.view.snapshot_id is not None
    assert result.checkpoint is not None
    assert result.checkpoint.snapshot_id == result.view.snapshot_id


def test_invalid_typed_value_fails_before_operation_is_started(tmp_path: Path) -> None:
    storage, prefix, dataset = _dataset(tmp_path)
    row = _row(storage, prefix.prefix_id, b"one", score=float("inf"))

    with pytest.raises(ValidationError):
        dataset.commit(
            branch="main",
            base=dataset.open_branch(),
            frame=pd.DataFrame([row]),
            schema_additions=[ColumnSpec("score", PrimitiveFieldType("double"))],
        )

    assert dataset.open_branch().snapshot_id is None


def test_commit_rejects_duplicate_frame_columns_before_operation_is_started(tmp_path: Path) -> None:
    storage, prefix, dataset = _dataset(tmp_path)
    row = _row(storage, prefix.prefix_id, b"one")
    frame = pd.DataFrame([row])
    frame = pd.concat([frame, frame[["relative_path"]]], axis="columns")
    table = dataset._manager.catalog.load_table(dataset.table_identifier)  # pyright: ignore[reportPrivateUsage]
    snapshots_before = tuple(snapshot.snapshot_id for snapshot in table.snapshots())

    with pytest.raises(ValidationError, match="duplicate"):
        dataset.commit(branch="main", base=dataset.open_branch(), frame=frame)

    table = dataset._manager.catalog.load_table(dataset.table_identifier)  # pyright: ignore[reportPrivateUsage]
    assert tuple(snapshot.snapshot_id for snapshot in table.snapshots()) == snapshots_before
    assert dataset.open_branch().snapshot_id is None
    assert dataset._manager.recover_operations() == 0  # pyright: ignore[reportPrivateUsage]


def test_add_column_is_recovered_as_durable_schema_operation(tmp_path: Path) -> None:
    storage, _, dataset = _dataset(tmp_path)

    def interrupt(_operation_id: str, phase: str) -> None:
        if phase == "schema_updated":
            raise RuntimeError("injected schema interruption")

    interrupted = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage, operation_hook=interrupt)
    interrupted_dataset = interrupted.open_repo(name="Vision").open_dataset(name="Raw")
    fixed = interrupted_dataset.open_branch()
    with pytest.raises(RuntimeError, match="schema interruption"):
        interrupted_dataset.schema.add_column(
            branch="main", base=fixed, column=ColumnSpec("score", PrimitiveFieldType("long"))
        )
    with pytest.raises(ConflictError):
        fixed.scan()
    with pytest.raises(ConflictError):
        interrupted._get_view_row(  # pyright: ignore[reportPrivateUsage]
            view=fixed,
            asset_id="sha256:" + "0" * 64,
        )

    recovered = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert recovered.recover_operations() == 1
    recovered_dataset = recovered.open_repo(name="Vision").open_dataset(name="Raw")
    assert recovered_dataset.schema.get_column(name="score").field_type == PrimitiveFieldType("long")


def test_snapshotless_empty_checkpoint_recovers_from_early_interruption(tmp_path: Path) -> None:
    storage, _, dataset = _dataset(tmp_path)
    columns = [column.name for column in dataset.schema.list_columns()]

    def interrupt(_operation_id: str, phase: str) -> None:
        if phase == "pending_vectors_written":
            raise RuntimeError("early interruption")

    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage, operation_hook=interrupt)
    interrupted = manager.open_repo(name="Vision").open_dataset(name="Raw")
    with pytest.raises(RuntimeError, match="early"):
        interrupted.commit(
            branch="main",
            base=interrupted.open_branch(),
            frame=pd.DataFrame(columns=columns),
            checkpoint_name="empty-v1",
        )

    recovered = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert recovered.recover_operations() == 1
    restored = recovered.open_repo(name="Vision").open_dataset(name="Raw")
    assert restored.open_branch().snapshot_id == restored.open_checkpoint(name="empty-v1").snapshot_id


def test_commit_rejects_invalid_empty_replace_patch_and_checkpoint_names(tmp_path: Path) -> None:
    storage, prefix, dataset = _dataset(tmp_path)
    row = _row(storage, prefix.prefix_id, b"one")
    base = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row])).view

    with pytest.raises(ValidationError, match="every Physical Schema"):
        dataset.commit(branch="main", base=base, frame=pd.DataFrame())
    with pytest.raises(ValidationError, match="non-empty"):
        dataset.commit(
            branch="main", base=base, frame=pd.DataFrame([{"asset_id": row["asset_id"]}]), mode="patch", fields=[]
        )
    with pytest.raises(NameConflictError, match="main"):
        dataset.commit(branch="main", base=base, frame=pd.DataFrame([row]), checkpoint_name="main")


def test_commit_schema_addition_rechecks_vector_namespace(tmp_path: Path) -> None:
    storage, prefix, dataset = _dataset(tmp_path)
    dataset._manager.model_manager.register(  # pyright: ignore[reportPrivateUsage]
        ModelDefinition(
            model_id="clip",
            provider="test",
            artifact_uri="memory://clip",
            artifact_revision="v1",
            artifact_checksum="sha256:" + "1" * 64,
            dimension=2,
            dtype="float32",
            config={},
        )
    )
    dataset.open_branch().repo.schema.add_vector(name="Score", model_id="clip", distance="cosine")
    row = _row(storage, prefix.prefix_id, b"one", score=1)
    with pytest.raises(ValidationError, match="VectorField"):
        dataset.commit(
            branch="main",
            base=dataset.open_branch(),
            frame=pd.DataFrame([row]),
            schema_additions=[ColumnSpec("score", PrimitiveFieldType("long"))],
        )


def test_checkpoint_name_conflict_does_not_leave_pending_operation(tmp_path: Path) -> None:
    storage, prefix, dataset = _dataset(tmp_path)
    row = _row(storage, prefix.prefix_id, b"one")
    view = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row])).view
    dataset.create_checkpoint(name="v1", source=view)
    with pytest.raises(NameConflictError):
        dataset.create_checkpoint(name="v1", source=view)
    assert dataset.open_branch().snapshot_id == view.snapshot_id


def test_recovery_reuses_temporary_ref_created_before_intent_update(tmp_path: Path) -> None:
    storage, prefix, dataset = _dataset(tmp_path)
    first = _row(storage, prefix.prefix_id, b"one")
    base = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([first])).view
    holder: dict[str, object] = {}

    def interrupt(operation_id: str, phase: str) -> None:
        if phase == "pending_vectors_written":
            manager = cast(DatasetManager, holder["manager"])
            current = cast(Dataset, holder["dataset"])
            table = manager.catalog.load_table(current.table_identifier)
            table.manage_snapshots().create_branch(base.snapshot_id, f"op_{operation_id}").commit()
            raise RuntimeError("temporary ref interruption")

    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage, operation_hook=interrupt)
    current = manager.open_repo(name="Vision").open_dataset(name="Raw")
    holder.update(manager=manager, dataset=current)
    second = _row(storage, prefix.prefix_id, b"two")
    with pytest.raises(RuntimeError, match="temporary ref"):
        current.commit(branch="main", base=current.open_branch(), frame=pd.DataFrame([second]), mode="upsert")

    recovered = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert recovered.recover_operations() == 1
    assert recovered.open_repo(name="Vision").open_dataset(name="Raw").open_branch().count() == 2
