from pathlib import Path

import pytest

from image_gallery.dataset_manager import (
    ConflictError,
    DatasetManager,
    NameConflictError,
    ValidationError,
    VectorCommit,
    VectorValidationItem,
)
from image_gallery.storage_manager import StorageManager


def make_view(tmp_path: Path):  # pyright: ignore[reportUnknownParameterType]
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Raw")
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"image")
    row = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": prefix.prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
    }
    view = dataset.commit(branch="main", base=dataset.open_branch(), rows=[row]).view
    return repo, dataset, view, stored.asset_id


def test_vector_field_is_repo_scoped_and_locked(tmp_path: Path) -> None:
    repo, _, _, _ = make_view(tmp_path)
    validation_set = [VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))]

    field = repo.create_vector_field(
        name="clip",
        dimension=2,
        distance="cosine",
        validation_set=validation_set,
    )

    assert repo.open_vector_field(name="CLIP") == field
    assert field.numeric_type == "float32"
    assert field.validation_set == tuple(validation_set)
    assert not hasattr(field, "update")
    assert repo.get_vector_field(vector_field_id=field.vector_field_id) == field
    assert repo.list_vector_fields() == [field]


@pytest.mark.parametrize("distance", ["", "euclidean", "manhattan"])
def test_vector_field_rejects_unknown_distance(tmp_path: Path, distance: str) -> None:
    repo, _, _, _ = make_view(tmp_path)

    with pytest.raises(ValidationError, match="supported distance"):
        repo.create_vector_field(
            name="invalid",
            dimension=2,
            distance=distance,
            validation_set=[VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))],
        )


def test_vector_field_rejects_unknown_numeric_type(tmp_path: Path) -> None:
    repo, _, _, _ = make_view(tmp_path)

    with pytest.raises(ValidationError, match="numeric_type"):
        repo.create_vector_field(
            name="invalid",
            dimension=2,
            numeric_type="float64",
            distance="cosine",
            validation_set=[VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))],
        )


def test_vector_field_name_is_unique_only_within_repo(tmp_path: Path) -> None:
    repo, _, _, _ = make_view(tmp_path)
    other = repo._manager.create_repo(name="Other")
    validation_set = [VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))]
    repo.create_vector_field(name="clip", dimension=2, distance="cosine", validation_set=validation_set)

    with pytest.raises(NameConflictError):
        repo.create_vector_field(name="CLIP", dimension=2, distance="cosine", validation_set=validation_set)

    assert (
        other.create_vector_field(
            name="clip",
            dimension=2,
            distance="cosine",
            validation_set=validation_set,
        ).repo_id
        == other.repo_id
    )


def test_vector_write_requires_complete_validation_outputs(tmp_path: Path) -> None:
    repo, _, view, asset_id = make_view(tmp_path)
    field = repo.create_vector_field(
        name="clip",
        dimension=2,
        distance="cosine",
        validation_set=[VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))],
    )
    with pytest.raises(ValidationError):
        field.write(source=view, items={asset_id: (1.0, 2.0)}, validation_outputs=[])

    with pytest.raises(ValidationError):
        field.write(source=view, items={asset_id: (1.0,)}, validation_outputs=[(0.1, 0.2)])

    with pytest.raises(ValidationError):
        field.write(
            source=view,
            items={asset_id: (1.0, 2.0)},
            validation_outputs=[(float("nan"), 0.2)],
        )
    assert field.get(asset_id=asset_id) is None


def test_vector_write_skips_then_explicitly_overwrites_current_value(tmp_path: Path) -> None:
    repo, _, view, asset_id = make_view(tmp_path)
    field = repo.create_vector_field(
        name="clip",
        dimension=2,
        distance="cosine",
        validation_set=[VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))],
    )
    inserted = field.write(
        source=view,
        items={asset_id: (1.0, 2.0)},
        validation_outputs=[(0.1, 0.2)],
    )
    skipped = field.write(
        source=view,
        items={asset_id: (3.0, 4.0)},
        validation_outputs=[(0.1, 0.2)],
    )
    updated = field.write(
        source=view,
        items={asset_id: (3.0, 4.0)},
        validation_outputs=[(0.1, 0.2)],
        overwrite=True,
    )

    assert inserted.inserted == 1
    assert skipped.skipped == 1
    assert updated.updated == 1
    assert field.get(asset_id=asset_id) == (3.0, 4.0)


def test_vector_write_rejects_asset_not_in_source_view(tmp_path: Path) -> None:
    repo, _, view, _ = make_view(tmp_path)
    field = repo.create_vector_field(
        name="clip",
        dimension=2,
        distance="cosine",
        validation_set=[VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))],
    )

    with pytest.raises(ValidationError):
        field.write(
            source=view,
            items={"sha256:" + "0" * 64: (1.0, 2.0)},
            validation_outputs=[(0.1, 0.2)],
        )


def test_checkpoint_reads_repo_current_vector_without_new_snapshot(tmp_path: Path) -> None:
    repo, dataset, view, asset_id = make_view(tmp_path)
    checkpoint = dataset.create_checkpoint(name="raw", source=view)
    field = repo.create_vector_field(
        name="clip",
        dimension=2,
        distance="cosine",
        validation_set=[VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))],
    )
    snapshot_id = checkpoint.snapshot_id

    field.write(source=checkpoint, items={asset_id: (1.0, 2.0)}, validation_outputs=[(0.1, 0.2)])
    field.write(
        source=checkpoint,
        items={asset_id: (3.0, 4.0)},
        validation_outputs=[(0.1, 0.2)],
        overwrite=True,
    )

    assert field.get(asset_id=asset_id) == (3.0, 4.0)
    assert dataset.open_checkpoint(name="raw").snapshot_id == snapshot_id


def test_repo_current_vector_is_shared_by_dataset_views_and_not_rolled_back(tmp_path: Path) -> None:
    repo, dataset, view, asset_id = make_view(tmp_path)
    checkpoint = dataset.create_checkpoint(name="raw", source=view)
    field = repo.create_vector_field(
        name="clip",
        dimension=2,
        distance="cosine",
        validation_set=[VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))],
    )
    field.write(source=view, items={asset_id: (1.0, 2.0)}, validation_outputs=[(0.1, 0.2)])
    current = dataset.commit(branch="main", base=view, rows=[]).view
    dataset.rollback(branch="main", base=current, checkpoint=checkpoint)

    assert field.get(asset_id=asset_id) == (1.0, 2.0)
    assert checkpoint.get_row(asset_id=asset_id)["asset_id"] == asset_id


def test_combined_commit_accepts_candidate_member_and_publishes_data_and_vector(tmp_path: Path) -> None:
    storage = StorageManager()
    manager = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Raw")
    field = repo.create_vector_field(
        name="clip",
        dimension=2,
        distance="cosine",
        validation_set=[VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))],
    )
    color_field = repo.create_vector_field(
        name="color",
        dimension=2,
        distance="l2",
        validation_set=[VectorValidationItem(probe=b"color", expected=(0.3, 0.4))],
    )
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"new")
    row = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": prefix.prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
    }

    result = dataset.commit(
        branch="main",
        base=dataset.open_branch(),
        rows=[row],
        vectors=[
            VectorCommit(
                field=field,
                items={stored.asset_id: (1.0, 2.0)},
                validation_outputs=[(0.1, 0.2)],
            ),
            VectorCommit(
                field=color_field,
                items={stored.asset_id: (3.0, 4.0)},
                validation_outputs=[(0.3, 0.4)],
            ),
        ],
    )

    assert result.view.scan() == [row]
    assert field.get(asset_id=stored.asset_id) == (1.0, 2.0)
    assert color_field.get(asset_id=stored.asset_id) == (3.0, 4.0)


def test_combined_commit_validation_failure_publishes_neither_side(tmp_path: Path) -> None:
    repo, dataset, view, asset_id = make_view(tmp_path)
    field = repo.create_vector_field(
        name="clip",
        dimension=2,
        distance="cosine",
        validation_set=[VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))],
    )

    with pytest.raises(ValidationError):
        dataset.commit(
            branch="main",
            base=view,
            rows=[],
            vectors=[
                VectorCommit(
                    field=field,
                    items={asset_id: (1.0, 2.0)},
                    validation_outputs=[(9.0, 9.0)],
                )
            ],
        )

    assert dataset.open_branch().snapshot_id == view.snapshot_id
    assert field.get(asset_id=asset_id) is None


def test_combined_commit_recovers_after_candidate_publish_interruption(tmp_path: Path) -> None:
    storage = StorageManager()

    def fail_after_candidate(_operation_id: str, phase: str) -> None:
        if phase == "candidate_written":
            raise RuntimeError("injected candidate interruption")

    interrupted = DatasetManager.local(
        root=tmp_path / "backend",
        storage_manager=storage,
        operation_hook=fail_after_candidate,
    )
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = interrupted.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Raw")
    field = repo.create_vector_field(
        name="clip",
        dimension=2,
        distance="cosine",
        validation_set=[VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))],
    )
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"new")
    row = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": prefix.prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
    }
    base = dataset.open_branch()

    with pytest.raises(RuntimeError, match="injected"):
        dataset.commit(
            branch="main",
            base=base,
            rows=[row],
            vectors=[
                VectorCommit(
                    field=field,
                    items={stored.asset_id: (1.0, 2.0)},
                    validation_outputs=[(0.1, 0.2)],
                )
            ],
        )
    with pytest.raises(ConflictError, match="reconciling"):
        dataset.open_branch()
    with pytest.raises(ConflictError, match="active combined commit"):
        field.write(
            source=base,
            items={},
            validation_outputs=[(0.1, 0.2)],
        )

    recovered = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert recovered.recover_operations() == 1
    recovered_repo = recovered.open_repo(name="Vision")
    assert recovered_repo.open_dataset(name="Raw").open_branch().scan() == [row]
    assert recovered_repo.open_vector_field(name="clip").get(asset_id=stored.asset_id) == (1.0, 2.0)


def test_combined_commit_recovers_after_pending_vector_interruption(tmp_path: Path) -> None:
    storage = StorageManager()

    def fail_after_pending(_operation_id: str, phase: str) -> None:
        if phase == "pending_vectors_written":
            raise RuntimeError("injected pending interruption")

    manager = DatasetManager.local(
        root=tmp_path / "backend",
        storage_manager=storage,
        operation_hook=fail_after_pending,
    )
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Raw")
    field = repo.create_vector_field(
        name="clip",
        dimension=2,
        distance="cosine",
        validation_set=[VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))],
    )
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"new")
    row = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": prefix.prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
    }

    with pytest.raises(RuntimeError, match="pending"):
        dataset.commit(
            branch="main",
            base=dataset.open_branch(),
            rows=[row],
            vectors=[
                VectorCommit(
                    field=field,
                    items={stored.asset_id: (1.0, 2.0)},
                    validation_outputs=[(0.1, 0.2)],
                )
            ],
        )

    recovered = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert recovered.recover_operations() == 1
    recovered_repo = recovered.open_repo(name="Vision")
    assert recovered_repo.open_dataset(name="Raw").open_branch().scan() == [row]
    assert recovered_repo.open_vector_field(name="clip").get(asset_id=stored.asset_id) == (1.0, 2.0)


def test_combined_commit_publishes_both_sides_atomically_before_notification(tmp_path: Path) -> None:
    storage = StorageManager()

    def fail_before_finalize(_operation_id: str, phase: str) -> None:
        if phase == "vectors_published":
            raise RuntimeError("injected finalize interruption")

    manager = DatasetManager.local(
        root=tmp_path / "backend",
        storage_manager=storage,
        operation_hook=fail_before_finalize,
    )
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Raw")
    field = repo.create_vector_field(
        name="clip",
        dimension=2,
        distance="cosine",
        validation_set=[VectorValidationItem(probe=b"fixed", expected=(0.1, 0.2))],
    )
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"new")
    row = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": prefix.prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
    }

    with pytest.raises(RuntimeError, match="finalize"):
        dataset.commit(
            branch="main",
            base=dataset.open_branch(),
            rows=[row],
            vectors=[
                VectorCommit(
                    field=field,
                    items={stored.asset_id: (1.0, 2.0)},
                    validation_outputs=[(0.1, 0.2)],
                )
            ],
        )
    assert dataset.open_branch().scan() == [row]
    assert field.get(asset_id=stored.asset_id) == (1.0, 2.0)

    recovered = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert recovered.recover_operations() == 0
    recovered_repo = recovered.open_repo(name="Vision")
    assert recovered_repo.open_dataset(name="Raw").open_branch().scan() == [row]
    assert recovered_repo.open_vector_field(name="clip").get(asset_id=stored.asset_id) == (1.0, 2.0)
