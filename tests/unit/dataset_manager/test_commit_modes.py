from pathlib import Path

import pandas as pd
import pytest

from image_gallery.dataset_manager import (
    ColumnSpec,
    ConflictError,
    DatasetManager,
    PrimitiveFieldType,
    ValidationError,
)
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

    recovered = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert recovered.recover_operations() == 1
    recovered_dataset = recovered.open_repo(name="Vision").open_dataset(name="Raw")
    assert recovered_dataset.schema.get_column(name="score").field_type == PrimitiveFieldType("long")
