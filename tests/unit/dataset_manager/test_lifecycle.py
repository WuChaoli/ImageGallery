from pathlib import Path

import pandas as pd
import pytest

from image_gallery.dataset_manager import ConflictError, DatasetManager, NameConflictError, ValidationError
from image_gallery.storage_manager import StorageManager


def setup_dataset(tmp_path: Path):  # pyright: ignore[reportUnknownParameterType]
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Raw")

    def row(data: bytes) -> dict[str, object]:
        stored = storage.write_managed(prefix_id=prefix.prefix_id, data=data)
        return {
            "asset_id": stored.asset_id,
            "storage_prefix_id": prefix.prefix_id,
            "relative_path": stored.relative_path,
            "source_uri": None,
            "tag_ids": [],
        }

    return repo, dataset, row


def test_branch_rolls_back_only_to_ancestor_checkpoint(tmp_path: Path) -> None:
    _, dataset, row = setup_dataset(tmp_path)
    first = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row(b"one")])).view
    raw = dataset.create_checkpoint(name="raw", source=first)
    second = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row(b"two")])).view

    rolled_back = dataset.rollback(branch="main", base=second, checkpoint=raw)

    assert rolled_back.scan().equals(first.scan())


def test_rollback_rejects_stale_base(tmp_path: Path) -> None:
    _, dataset, row = setup_dataset(tmp_path)
    first = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row(b"one")])).view
    raw = dataset.create_checkpoint(name="raw", source=first)
    current = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row(b"two")])).view
    dataset.commit(branch="main", base=current, frame=pd.DataFrame([row(b"three")]))

    with pytest.raises(ConflictError):
        dataset.rollback(branch="main", base=current, checkpoint=raw)


def test_tag_definition_rename_and_archive_do_not_change_dataset_snapshot(tmp_path: Path) -> None:
    repo, dataset, row = setup_dataset(tmp_path)
    tag = repo.create_tag(name="cat")
    tagged = row(b"one")
    tagged["tag_ids"] = [tag.tag_id]
    view = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([tagged])).view

    renamed = repo.rename_tag(tag_id=tag.tag_id, name="animal")
    archived = repo.archive_tag(tag_id=tag.tag_id)

    assert renamed.name == "animal"
    assert archived.archived is True
    assert dataset.open_branch().snapshot_id == view.snapshot_id
    assert dataset.open_branch().scan().iloc[0]["tag_ids"] == [tag.tag_id]
    new_row = row(b"two")
    new_row["tag_ids"] = [tag.tag_id]
    with pytest.raises(ValidationError):
        dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([new_row]))


def test_tag_definition_identity_is_repo_scoped_and_name_is_unique(tmp_path: Path) -> None:
    repo, _, _ = setup_dataset(tmp_path)
    other = repo._manager.create_repo(name="Other")
    first = repo.create_tag(name="Cat")
    other_tag = other.create_tag(name="cat")

    with pytest.raises(NameConflictError):
        repo.create_tag(name="CAT")
    renamed = repo.rename_tag(tag_id=first.tag_id, name="Animal")

    assert renamed.tag_id == first.tag_id
    assert other_tag.tag_id != first.tag_id


def test_checkpoint_and_non_ancestor_rollback_enforce_lineage(tmp_path: Path) -> None:
    _, dataset, row = setup_dataset(tmp_path)
    first = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row(b"one")])).view
    raw = dataset.create_checkpoint(name="raw", source=first)
    dataset.create_branch(name="experiment", source=raw)
    experiment = dataset.commit(
        branch="experiment",
        base=dataset.open_branch(name="experiment"),
        frame=pd.DataFrame([row(b"experiment")]),
    ).view
    experiment_checkpoint = dataset.create_checkpoint(name="experiment-state", source=experiment)
    main = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row(b"main")])).view

    with pytest.raises(ValidationError, match="ancestor"):
        dataset.rollback(branch="main", base=main, checkpoint=experiment_checkpoint)


def test_checkpoint_rejects_stale_branch_view(tmp_path: Path) -> None:
    _, dataset, row = setup_dataset(tmp_path)
    stale = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row(b"one")])).view
    dataset.commit(branch="main", base=stale, frame=pd.DataFrame([row(b"two")]))

    with pytest.raises(ConflictError):
        dataset.create_checkpoint(name="stale", source=stale)


def test_plain_commit_recovers_temporary_ref_before_branch_publish(tmp_path: Path) -> None:
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Raw")

    def row(data: bytes) -> dict[str, object]:
        stored = storage.write_managed(prefix_id=prefix.prefix_id, data=data)
        return {
            "asset_id": stored.asset_id,
            "storage_prefix_id": prefix.prefix_id,
            "relative_path": stored.relative_path,
            "source_uri": None,
            "tag_ids": [],
        }

    dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row(b"one")]))

    def fail_after_candidate(_operation_id: str, phase: str) -> None:
        if phase == "candidate_written":
            raise RuntimeError("injected candidate interruption")

    interrupted = DatasetManager.local(
        root=tmp_path / "backend",
        storage_manager=storage,
        operation_hook=fail_after_candidate,
    )
    interrupted_dataset = interrupted.open_repo(name="Vision").open_dataset(name="Raw")
    interrupted_base = interrupted_dataset.open_branch()
    with pytest.raises(RuntimeError, match="injected"):
        interrupted_dataset.commit(branch="main", base=interrupted_base, frame=pd.DataFrame([row(b"two")]))

    recovered = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert recovered.recover_operations() == 1
    recovered_dataset = recovered.open_repo(name="Vision").open_dataset(name="Raw")
    assert recovered_dataset.open_branch().count() == 2
    assert not any(name.startswith("op_") for name in recovered.catalog.load_table(dataset.table_identifier).refs())


def test_checkpoint_and_rollback_recover_after_ref_publish(tmp_path: Path) -> None:
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Raw")

    def row(data: bytes) -> dict[str, object]:
        stored = storage.write_managed(prefix_id=prefix.prefix_id, data=data)
        return {
            "asset_id": stored.asset_id,
            "storage_prefix_id": prefix.prefix_id,
            "relative_path": stored.relative_path,
            "source_uri": None,
            "tag_ids": [],
        }

    first = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row(b"one")])).view

    def fail_checkpoint(_operation_id: str, phase: str) -> None:
        if phase == "checkpoint_created":
            raise RuntimeError("checkpoint interruption")

    interrupted = DatasetManager.local(
        root=tmp_path / "backend",
        storage_manager=storage,
        operation_hook=fail_checkpoint,
    )
    interrupted_dataset = interrupted.open_repo(name="Vision").open_dataset(name="Raw")
    interrupted_first = interrupted_dataset.open_branch()
    with pytest.raises(RuntimeError, match="checkpoint"):
        interrupted_dataset.create_checkpoint(name="raw", source=interrupted_first)

    recovered = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert recovered.recover_operations() == 1
    recovered_dataset = recovered.open_repo(name="Vision").open_dataset(name="Raw")
    recovered_dataset.commit(
        branch="main",
        base=recovered_dataset.open_branch(),
        frame=pd.DataFrame([row(b"two")]),
    )

    def fail_rollback(_operation_id: str, phase: str) -> None:
        if phase == "rollback_published":
            raise RuntimeError("rollback interruption")

    interrupted_rollback = DatasetManager.local(
        root=tmp_path / "backend",
        storage_manager=storage,
        operation_hook=fail_rollback,
    )
    rollback_dataset = interrupted_rollback.open_repo(name="Vision").open_dataset(name="Raw")
    with pytest.raises(RuntimeError, match="rollback"):
        rollback_dataset.rollback(
            branch="main",
            base=rollback_dataset.open_branch(),
            checkpoint=rollback_dataset.open_checkpoint(name="raw"),
        )

    final = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert final.recover_operations() == 1
    assert final.open_repo(name="Vision").open_dataset(name="Raw").open_branch().scan().equals(first.scan())
