from pathlib import Path

import pandas as pd
import pytest

from image_gallery.dataset_manager import (
    ConflictError,
    Dataset,
    DatasetManager,
    DatasetRepo,
    DatasetView,
    NameConflictError,
    ObjectNotFoundError,
    ValidationError,
)
from image_gallery.storage_manager import StorageManager, StoragePrefix


def make_dataset(tmp_path: Path) -> tuple[StorageManager, StoragePrefix, DatasetRepo, Dataset]:
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Raw")
    return storage, prefix, repo, dataset


def make_row(storage: StorageManager, prefix_id: str, data: bytes, **extra: object) -> dict[str, object]:
    stored = storage.write_managed(prefix_id=prefix_id, data=data)
    return {
        "asset_id": stored.asset_id,
        "storage_prefix_id": stored.storage_prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
        **extra,
    }


def test_commit_creates_fixed_view_and_noop_does_not_advance(tmp_path: Path) -> None:
    storage, prefix, _, dataset = make_dataset(tmp_path)
    base = dataset.open_branch(name="main")
    row = make_row(storage, prefix.prefix_id, b"one")

    committed = dataset.commit(branch="main", base=base, frame=pd.DataFrame([row]))
    noop = dataset.commit(branch="main", base=committed.view, frame=pd.DataFrame([row]))

    assert base.scan().empty
    assert committed.inserted == 1
    assert committed.updated == 0
    assert committed.view.scan().to_dict(orient="records") == [row]
    assert noop.changed is False
    assert noop.view.snapshot_id == committed.view.snapshot_id


def test_commit_rejects_stale_branch_view(tmp_path: Path) -> None:
    storage, prefix, _, dataset = make_dataset(tmp_path)
    base = dataset.open_branch(name="main")
    dataset.commit(branch="main", base=base, frame=pd.DataFrame([make_row(storage, prefix.prefix_id, b"one")]))

    with pytest.raises(ConflictError):
        dataset.commit(branch="main", base=base, frame=pd.DataFrame([make_row(storage, prefix.prefix_id, b"two")]))


def test_checkpoint_is_fixed_and_branch_diverges(tmp_path: Path) -> None:
    storage, prefix, _, dataset = make_dataset(tmp_path)
    first = make_row(storage, prefix.prefix_id, b"one")
    main = dataset.commit(branch="main", base=dataset.open_branch(name="main"), frame=pd.DataFrame([first])).view
    checkpoint = dataset.create_checkpoint(name="raw", source=main)
    dataset.create_branch(name="experiment", source=checkpoint)
    second = make_row(storage, prefix.prefix_id, b"two")

    experiment = dataset.commit(
        branch="experiment",
        base=dataset.open_branch(name="experiment"),
        frame=pd.DataFrame([second]),
        mode="upsert",
    ).view

    assert dataset.list_checkpoints() == ["raw"]
    assert dataset.open_checkpoint(name="raw").scan().to_dict(orient="records") == [first]
    assert dataset.open_branch(name="main").scan().to_dict(orient="records") == [first]
    assert set(experiment.scan()["asset_id"]) == {first["asset_id"], second["asset_id"]}


def test_branch_can_start_from_stale_fixed_branch_view(tmp_path: Path) -> None:
    storage, prefix, _, dataset = make_dataset(tmp_path)
    first_row = make_row(storage, prefix.prefix_id, b"one")
    first = dataset.commit(
        branch="main",
        base=dataset.open_branch(name="main"),
        frame=pd.DataFrame([first_row]),
    ).view
    dataset.commit(
        branch="main",
        base=dataset.open_branch(name="main"),
        frame=pd.DataFrame([make_row(storage, prefix.prefix_id, b"two")]),
    )

    experiment = dataset.create_branch(name="experiment", source=first)

    assert experiment.snapshot_id == first.snapshot_id
    assert experiment.scan().to_dict(orient="records") == [first_row]


def test_branch_validates_source_and_prechecks_all_ref_names(tmp_path: Path) -> None:
    storage, prefix, repo, dataset = make_dataset(tmp_path)
    source = dataset.commit(
        branch="main",
        base=dataset.open_branch(),
        frame=pd.DataFrame([make_row(storage, prefix.prefix_id, b"one")]),
    ).view
    dataset.create_checkpoint(name="reserved", source=source)
    other = repo.create_dataset(name="Other")

    with pytest.raises(NameConflictError, match="reserved"):
        dataset.create_branch(name="reserved", source=source)
    with pytest.raises(ValidationError):
        dataset.create_branch(name="cross-dataset", source=other.open_branch())

    missing_snapshot = dataset._manager._make_view(  # pyright: ignore[reportPrivateUsage]
        repo_id=source.repo_id,
        dataset_id=source.dataset_id,
        snapshot_id=source.snapshot_id + 10_000 if source.snapshot_id is not None else 10_000,
        ref_name=source.ref_name,
        ref_type=source.ref_type,
    )
    with pytest.raises(ValidationError, match="Snapshot"):
        dataset.create_branch(name="missing-snapshot", source=missing_snapshot)


def test_view_owner_navigation_uses_immutable_ids_and_visibility(tmp_path: Path) -> None:
    _, _, repo, dataset = make_dataset(tmp_path)
    view = dataset.open_branch()

    assert view.dataset.dataset_id == dataset.dataset_id
    assert view.dataset.repo_id == repo.repo_id
    assert view.repo.repo_id == repo.repo_id

    missing = dataset._manager._make_view(  # pyright: ignore[reportPrivateUsage]
        repo_id=repo.repo_id,
        dataset_id="missing",
        snapshot_id=None,
        ref_name="main",
        ref_type="branch",
    )
    with pytest.raises(ObjectNotFoundError, match="missing"):
        _ = missing.dataset
    with pytest.raises(ObjectNotFoundError, match="missing"):
        _ = missing.repo

    forged = DatasetView(
        repo_id=repo.repo_id,
        dataset_id=dataset.dataset_id,
        snapshot_id=view.snapshot_id,
        ref_name=view.ref_name,
        ref_type=view.ref_type,
        _manager=dataset._manager,  # pyright: ignore[reportPrivateUsage]
    )
    with pytest.raises(ValidationError, match="DatasetManager"):
        _ = forged.dataset
    with pytest.raises(ValidationError, match="DatasetManager"):
        _ = forged.repo

    tampered = DatasetView(
        repo_id=repo.repo_id,
        dataset_id=dataset.dataset_id,
        snapshot_id=view.snapshot_id,
        ref_name="other",
        ref_type=view.ref_type,
        _manager=dataset._manager,  # pyright: ignore[reportPrivateUsage]
        _provenance=view._provenance,  # pyright: ignore[reportPrivateUsage]
    )
    with pytest.raises(ValidationError, match="DatasetManager"):
        _ = tampered.dataset
    with pytest.raises(ValidationError, match="DatasetManager"):
        tampered.scan()


def test_branch_rejects_view_bound_to_another_manager(tmp_path: Path) -> None:
    storage, prefix, repo, dataset = make_dataset(tmp_path)
    source = dataset.commit(
        branch="main",
        base=dataset.open_branch(),
        frame=pd.DataFrame([make_row(storage, prefix.prefix_id, b"one")]),
    ).view
    second_manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    second_dataset = second_manager.open_repo(name=repo.name).open_dataset(name=dataset.name)

    with pytest.raises(ValidationError):
        second_dataset.create_branch(name="experiment", source=source)


def test_tag_assignments_are_dataset_versioned(tmp_path: Path) -> None:
    storage, prefix, repo, dataset = make_dataset(tmp_path)
    tag = repo.create_tag(name="cat", color="#ffffff")
    row = make_row(storage, prefix.prefix_id, b"one", tag_ids=[tag.tag_id, tag.tag_id])

    committed = dataset.commit(branch="main", base=dataset.open_branch(name="main"), frame=pd.DataFrame([row])).view

    assert committed.scan().iloc[0]["tag_ids"] == [tag.tag_id]


def test_same_asset_can_have_different_tags_across_datasets(tmp_path: Path) -> None:
    storage, prefix, repo, first = make_dataset(tmp_path)
    second = repo.create_dataset(name="Second")
    tag_a = repo.create_tag(name="a")
    tag_b = repo.create_tag(name="b")
    common = make_row(storage, prefix.prefix_id, b"same")

    first_view = first.commit(
        branch="main",
        base=first.open_branch(name="main"),
        frame=pd.DataFrame([{**common, "tag_ids": [tag_a.tag_id]}]),
    ).view
    second_view = second.commit(
        branch="main",
        base=second.open_branch(name="main"),
        frame=pd.DataFrame([{**common, "tag_ids": [tag_b.tag_id]}]),
    ).view

    assert first_view.scan().iloc[0]["tag_ids"] == [tag_a.tag_id]
    assert second_view.scan().iloc[0]["tag_ids"] == [tag_b.tag_id]


def test_view_reads_image_through_storage_manager(tmp_path: Path) -> None:
    storage, prefix, _, dataset = make_dataset(tmp_path)
    row = make_row(storage, prefix.prefix_id, b"image")
    view = dataset.commit(branch="main", base=dataset.open_branch(name="main"), frame=pd.DataFrame([row])).view

    assert view.read_image(asset_id=str(row["asset_id"])) == b"image"
    assert view.scan(fields=["asset_id"]).to_dict(orient="records") == [{"asset_id": row["asset_id"]}]
    assert view.get_row(asset_id=str(row["asset_id"])).to_dict() == row
    assert list(view.iter_images()) == [(row, b"image")]
    assert view.count() == 1
    assert view.preview(limit=1).to_dict(orient="records") == [row]


def test_image_io_ignores_source_uri_and_supports_explicit_integrity_check(tmp_path: Path) -> None:
    storage, prefix, _, dataset = make_dataset(tmp_path)
    storage.write_bytes(prefix_id=prefix.prefix_id, relative_path="external/image.jpg", data=b"image")
    stored = storage.verify_external(prefix_id=prefix.prefix_id, relative_path="external/image.jpg")
    row = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": stored.storage_prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": "https://invalid.example/not-used",
        "tag_ids": [],
    }
    view = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row])).view

    assert view.read_image(asset_id=str(row["asset_id"])) == b"image"
    assert view.verify_image(asset_id=str(row["asset_id"])) is True
    storage.write_bytes(
        prefix_id=prefix.prefix_id,
        relative_path=str(row["relative_path"]),
        data=b"changed",
        overwrite=True,
    )
    with pytest.raises(Exception, match="expected"):
        view.verify_image(asset_id=str(row["asset_id"]))


def test_physical_schema_only_adds_optional_business_columns(tmp_path: Path) -> None:
    storage, prefix, _, dataset = make_dataset(tmp_path)
    base = dataset.open_branch()

    current = dataset.schema.add_column(branch="main", base=base, name="split", field_type="string")
    row = make_row(storage, prefix.prefix_id, b"one", split="train")
    committed = dataset.commit(branch="main", base=current, frame=pd.DataFrame([row])).view

    assert committed.scan(fields=["asset_id", "split"]).to_dict(orient="records") == [
        {"asset_id": row["asset_id"], "split": "train"}
    ]
    with pytest.raises(ValidationError):
        dataset.schema.add_column(branch="main", base=committed, name="asset_id", field_type="string")
    with pytest.raises(ValidationError):
        dataset.schema.add_column(branch="main", base=committed, name="bad", field_type="object")


def test_schema_change_rejects_stale_branch_view(tmp_path: Path) -> None:
    storage, prefix, _, dataset = make_dataset(tmp_path)
    stale = dataset.open_branch()
    current = dataset.commit(
        branch="main",
        base=stale,
        frame=pd.DataFrame([make_row(storage, prefix.prefix_id, b"one")]),
    ).view

    with pytest.raises(ConflictError):
        dataset.schema.add_column(branch="main", base=stale, name="split", field_type="string")

    assert dataset.schema.add_column(branch="main", base=current, name="split", field_type="string") == current


def test_view_rejects_unknown_projection_and_is_immutable(tmp_path: Path) -> None:
    _, _, _, dataset = make_dataset(tmp_path)
    view = dataset.open_branch()

    with pytest.raises(ValidationError):
        view.scan(fields=["unknown"])
    assert not hasattr(view, "commit")
    assert not hasattr(view, "create_branch")
    with pytest.raises(ObjectNotFoundError, match="missing"):
        view.get_row(asset_id="missing")


def test_commit_rejects_invalid_duplicate_and_wrongly_typed_rows(tmp_path: Path) -> None:
    storage, prefix, _, dataset = make_dataset(tmp_path)
    row = make_row(storage, prefix.prefix_id, b"one")

    with pytest.raises(ValidationError, match="asset_id"):
        dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([{**row, "asset_id": "bad"}]))
    with pytest.raises(ValidationError, match="Duplicate"):
        dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([row, row]))
    with pytest.raises(ValidationError, match="tag_ids"):
        dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([{**row, "tag_ids": "bad"}]))


def test_upsert_replaces_complete_row(tmp_path: Path) -> None:
    storage, prefix, _, dataset = make_dataset(tmp_path)
    base_row = make_row(storage, prefix.prefix_id, b"one")
    first = dataset.commit(branch="main", base=dataset.open_branch(), frame=pd.DataFrame([base_row])).view

    replacement = {**base_row, "source_uri": "source://updated"}
    result = dataset.commit(branch="main", base=first, frame=pd.DataFrame([replacement]), mode="upsert")

    assert result.inserted == 0
    assert result.updated == 1
    assert result.view.scan().to_dict(orient="records") == [replacement]
