from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import select

from image_gallery.dataset_manager import ConflictError, Dataset, DatasetManager
from image_gallery.dataset_manager.control import operations
from image_gallery.storage_manager import StorageManager


def setup_history(tmp_path: Path) -> tuple[DatasetManager, Dataset, list[int]]:
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Raw")
    snapshot_ids: list[int] = []
    for data in (b"one", b"two", b"three"):
        stored = storage.write_managed(prefix_id=prefix.prefix_id, data=data)
        row = {
            "asset_id": stored.asset_id,
            "storage_prefix_id": stored.storage_prefix_id,
            "relative_path": stored.relative_path,
            "source_uri": None,
            "tag_ids": [],
        }
        result = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row]))
        assert result.view.snapshot_id is not None
        snapshot_ids.append(result.view.snapshot_id)
    return manager, dataset, snapshot_ids


def operation_status(manager: DatasetManager, operation_id: str) -> str:
    with manager._engine.connect() as connection:  # pyright: ignore[reportPrivateUsage]
        status = connection.execute(
            select(operations.c.status).where(operations.c.operation_id == operation_id)
        ).scalar_one()
    return str(status)


def test_checkpoint_recovery_marks_mismatched_ref_failed(tmp_path: Path) -> None:
    manager, dataset, snapshot_ids = setup_history(tmp_path)
    table = manager.catalog.load_table(dataset.table_identifier)
    table.manage_snapshots().create_tag(snapshot_ids[1], "raw").commit()
    operation_id = manager._operations.start(  # pyright: ignore[reportPrivateUsage]
        kind="checkpoint",
        repo_id=dataset.repo_id,
        dataset_id=dataset.dataset_id,
        intent={
            "table_identifier": dataset.table_identifier,
            "checkpoint": "raw",
            "snapshot_id": snapshot_ids[0],
        },
    )

    with pytest.raises(ConflictError, match="raw"):
        manager.recover_operations()

    assert operation_status(manager, operation_id) == "failed"
    assert manager.recover_operations() == 0


def test_rollback_recovery_marks_diverged_head_failed(tmp_path: Path) -> None:
    manager, dataset, snapshot_ids = setup_history(tmp_path)
    operation_id = manager._operations.start(  # pyright: ignore[reportPrivateUsage]
        kind="rollback",
        repo_id=dataset.repo_id,
        dataset_id=dataset.dataset_id,
        intent={
            "table_identifier": dataset.table_identifier,
            "branch": "main",
            "base_snapshot_id": snapshot_ids[1],
            "target_snapshot_id": snapshot_ids[0],
        },
    )

    with pytest.raises(ConflictError, match="main"):
        manager.recover_operations()

    assert operation_status(manager, operation_id) == "failed"
    assert manager.recover_operations() == 0


def test_commit_checkpoint_recovery_marks_mismatched_ref_failed(tmp_path: Path) -> None:
    manager, dataset, snapshot_ids = setup_history(tmp_path)
    table = manager.catalog.load_table(dataset.table_identifier)
    table.manage_snapshots().create_tag(snapshot_ids[0], "release").commit()
    operation_id = manager._operations.start(  # pyright: ignore[reportPrivateUsage]
        kind="commit",
        repo_id=dataset.repo_id,
        dataset_id=dataset.dataset_id,
        intent={
            "repo_id": dataset.repo_id,
            "dataset_id": dataset.dataset_id,
            "table_identifier": dataset.table_identifier,
            "branch": "main",
            "base_snapshot_id": snapshot_ids[1],
            "candidate_snapshot_id": snapshot_ids[2],
            "temporary_ref": None,
            "rows": [],
            "data_changed": True,
            "schema_additions": [],
            "checkpoint_name": "release",
        },
    )

    with pytest.raises(ConflictError, match="release"):
        manager.recover_operations()

    assert operation_status(manager, operation_id) == "failed"
    with pytest.raises(ConflictError, match="reconciling"):
        dataset.open_branch()
    assert manager.recover_operations() == 0
