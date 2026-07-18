import threading
from pathlib import Path

import pandas as pd
import pytest

from image_gallery.dataset_manager import DatasetManager, NameConflictError, ValidationError
from image_gallery.model_manager import ModelDefinition, ModelManager
from image_gallery.storage_manager import ContentIntegrityError, StorageManager


class Runtime:
    def __init__(self) -> None:
        self.fail = False
        self.batch_sizes: list[int] = []

    def embed(self, images: list[bytes]) -> list[tuple[float, ...]]:
        self.batch_sizes.append(len(images))
        if self.fail:
            raise RuntimeError("injected inference failure")
        return [(float(len(value)), 1.0) for value in images]

    def close(self) -> None:
        pass


def setup_dataset(tmp_path: Path):  # pyright: ignore[reportUnknownParameterType]
    models = ModelManager(providers={"test": lambda _definition, _secrets: Runtime()})
    models.register(
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
    storage = StorageManager()
    manager = DatasetManager.local(
        root=tmp_path / "backend",
        storage_manager=storage,
        model_manager=models,
    )
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    dataset = repo.create_dataset(name="Raw")
    objects = [storage.write_managed(prefix_id=prefix.prefix_id, data=value) for value in (b"one", b"three")]
    frame = pd.DataFrame(
        [
            {
                "asset_id": item.asset_id,
                "storage_prefix_id": item.storage_prefix_id,
                "relative_path": item.relative_path,
                "source_uri": None,
                "tag_ids": [],
            }
            for item in objects
        ]
    )
    view = dataset.commit(branch="main", base=dataset.open_branch(), frame=frame).view
    return manager, repo, dataset, view, objects


def test_schema_facades_and_dataframe_io(tmp_path: Path) -> None:
    _, repo, dataset, view, objects = setup_dataset(tmp_path)
    dataset.schema.add_column(branch="main", base=view, name="split", field_type="string")
    field = repo.schema.add_vector(name="embedding", model_id="clip", distance="cosine")

    patched = dataset.commit(
        branch="main",
        base=dataset.open_branch(),
        frame=pd.DataFrame([{"asset_id": objects[0].asset_id, "split": "train"}]),
        fields=["split"],
    ).view
    assert list(patched.scan(fields=["asset_id", "split"]).columns) == ["asset_id", "split"]
    assert patched.get_row(asset_id=objects[0].asset_id)["split"] == "train"
    assert field.model_id == "clip"
    assert dataset.schema.list_columns()
    assert repo.schema.list_vectors() == [field]
    with pytest.raises(ValidationError):
        dataset.schema.add_column(branch="main", base=patched, name="embedding", field_type="string")
    with pytest.raises(ValidationError):
        repo.schema.add_vector(name="split", model_id="clip", distance="cosine")


def test_schema_names_conflict_after_trimming_and_casefolding(tmp_path: Path) -> None:
    _, repo, dataset, view, _ = setup_dataset(tmp_path)
    dataset.schema.add_column(branch="main", base=view, name=" Embedding ", field_type="string")

    with pytest.raises(ValidationError, match="conflicts"):
        repo.schema.add_vector(name="embedding", model_id="clip", distance="cosine")

    other = repo.create_dataset(name="Other")
    repo.schema.add_vector(name=" Features ", model_id="clip", distance="cosine")
    with pytest.raises(ValidationError, match="conflicts"):
        other.schema.add_column(
            branch="main",
            base=other.open_branch(),
            name="features",
            field_type="string",
        )


def test_vector_field_create_is_idempotent_only_for_same_frozen_definition(tmp_path: Path) -> None:
    manager, repo, _, _, _ = setup_dataset(tmp_path)

    first = repo.schema.add_vector(name=" embedding ", model_id="clip", distance="cosine")
    repeated = repo.schema.add_vector(name="EMBEDDING", model_id="clip", distance="cosine")

    assert repeated == first
    assert repeated._manager is manager  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(NameConflictError, match="EMBEDDING"):
        repo.schema.add_vector(name="EMBEDDING", model_id="clip", distance="dot")
    assert repo.schema.list_vectors() == [first]


def test_same_repo_concurrent_column_and_vector_name_has_single_winner(tmp_path: Path) -> None:
    _, repo, dataset, view, _ = setup_dataset(tmp_path)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def add_column() -> None:
        barrier.wait()
        try:
            dataset.schema.add_column(branch="main", base=view, name="Shared", field_type="string")
            outcomes.append("column")
        except ValidationError:
            outcomes.append("column-rejected")

    def add_vector() -> None:
        barrier.wait()
        try:
            repo.schema.add_vector(name=" shared ", model_id="clip", distance="cosine")
            outcomes.append("vector")
        except ValidationError:
            outcomes.append("vector-rejected")

    threads = [threading.Thread(target=add_column), threading.Thread(target=add_vector)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert all(not thread.is_alive() for thread in threads)
    assert sum(item in {"column", "vector"} for item in outcomes) == 1
    assert len(outcomes) == 2


def test_local_schema_lock_is_repo_scoped_and_reusable_after_failure(tmp_path: Path) -> None:
    manager, repo, _, _, _ = setup_dataset(tmp_path)
    other = manager.create_repo(name="Other")
    first_acquired = threading.Event()
    release_first = threading.Event()
    second_acquired = threading.Event()

    def hold_first_repo() -> None:
        with manager._repo_schema_lock(repo_id=repo.repo_id):  # pyright: ignore[reportPrivateUsage]
            first_acquired.set()
            release_first.wait(timeout=10)

    thread = threading.Thread(target=hold_first_repo)
    thread.start()
    assert first_acquired.wait(timeout=10)
    with manager._repo_schema_lock(repo_id=other.repo_id):  # pyright: ignore[reportPrivateUsage]
        second_acquired.set()
    assert second_acquired.is_set()
    release_first.set()
    thread.join(timeout=10)
    assert not thread.is_alive()

    with pytest.raises(RuntimeError, match="injected"):
        with manager._repo_schema_lock(repo_id=repo.repo_id):  # pyright: ignore[reportPrivateUsage]
            raise RuntimeError("injected")
    with manager._repo_schema_lock(repo_id=repo.repo_id):  # pyright: ignore[reportPrivateUsage]
        pass


def test_generate_embed_defaults_to_main_and_combines_vector_fields(tmp_path: Path) -> None:
    _, repo, dataset, view, objects = setup_dataset(tmp_path)
    repo.schema.add_vector(name="embedding", model_id="clip", distance="cosine")
    snapshot_id = view.snapshot_id

    result = dataset.generate_embed(field="embedding")

    assert result.source_snapshot_id == snapshot_id
    assert result.generated == 2
    assert result.updated == 0
    assert result.skipped == 0
    scanned = view.scan(fields=["asset_id", "embedding"])
    assert scanned["asset_id"].tolist() == sorted(item.asset_id for item in objects)
    assert {tuple(value) for value in scanned["embedding"]} == {(3.0, 1.0), (5.0, 1.0)}
    assert dataset.open_branch().snapshot_id == snapshot_id
    skipped = dataset.generate_embed(field="embedding")
    overwritten = dataset.generate_embed(field="embedding", overwrite=True)
    assert (skipped.generated, skipped.updated, skipped.skipped) == (0, 0, 2)
    assert (overwritten.generated, overwritten.updated, overwritten.skipped) == (0, 2, 0)
    assert dataset.open_branch().snapshot_id == snapshot_id


def test_generate_embed_batches_more_than_sixty_four_images(tmp_path: Path) -> None:
    manager, repo, dataset, view, objects = setup_dataset(tmp_path)
    prefix_id = objects[0].storage_prefix_id
    storage = manager.storage_manager
    more = [storage.write_managed(prefix_id=prefix_id, data=f"batch-{index}".encode()) for index in range(63)]
    rows = pd.DataFrame(
        [
            {
                "asset_id": item.asset_id,
                "storage_prefix_id": item.storage_prefix_id,
                "relative_path": item.relative_path,
                "source_uri": None,
                "tag_ids": [],
            }
            for item in more
        ]
    )
    expanded = dataset.commit(branch="main", base=view, frame=rows).view
    repo.schema.add_vector(name="embedding", model_id="clip", distance="cosine")

    result = dataset.generate_embed(field="embedding", source=expanded)

    runtime = manager.model_manager._runtimes["clip"]  # pyright: ignore[reportPrivateUsage]
    assert isinstance(runtime, Runtime)
    assert runtime.batch_sizes == [64, 1]
    assert result.generated == 65


def test_generate_embed_rejects_cross_dataset_view_and_direct_vector_commit(tmp_path: Path) -> None:
    _, repo, dataset, view, _ = setup_dataset(tmp_path)
    repo.schema.add_vector(name="embedding", model_id="clip", distance="cosine")
    other = repo.create_dataset(name="Other")

    with pytest.raises(ValidationError):
        other.generate_embed(field="embedding", source=view)
    with pytest.raises(ValidationError, match="generate_embed"):
        dataset.commit(
            branch="main",
            base=view,
            frame=pd.DataFrame([{"asset_id": view.scan().iloc[0]["asset_id"], "embedding": [1.0, 2.0]}]),
            fields=["embedding"],
        )


def test_dataframe_reads_handle_empty_vectors_and_fields_without_asset_id(tmp_path: Path) -> None:
    _, repo, dataset, view, objects = setup_dataset(tmp_path)
    repo.schema.add_vector(name="embedding", model_id="clip", distance="cosine")

    selected = view.get_rows(asset_ids=[objects[0].asset_id], fields=["source_uri"])
    assert list(selected.columns) == ["source_uri"]
    assert len(selected.index) == 1

    empty = repo.create_dataset(name="Empty").open_branch().scan(fields=["embedding"])
    assert list(empty.columns) == ["embedding"]
    assert empty.empty


def test_view_projection_keeps_field_order_and_uses_current_vectors(tmp_path: Path) -> None:
    _, repo, dataset, view, objects = setup_dataset(tmp_path)
    repo.schema.add_vector(name="embedding", model_id="clip", distance="cosine")

    before = view.scan(fields=["embedding", "source_uri", "asset_id"])
    dataset.generate_embed(field="embedding", source=view)
    after = view.scan(fields=["embedding", "source_uri", "asset_id"])

    assert list(before.columns) == ["embedding", "source_uri", "asset_id"]
    assert before["embedding"].isna().all()
    assert list(after.columns) == ["embedding", "source_uri", "asset_id"]
    assert after["embedding"].notna().all()
    assert after["asset_id"].tolist() == sorted(item.asset_id for item in objects)
    assert list(view.scan(fields=[]).columns) == list(view.scan().columns)


def test_generate_embed_rejects_ambiguous_source_before_storage_io(tmp_path: Path, monkeypatch) -> None:  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    manager, repo, dataset, view, _ = setup_dataset(tmp_path)
    repo.schema.add_vector(name="embedding", model_id="clip", distance="cosine")
    reads: list[tuple[str, str]] = []

    def record_read(*, prefix_id: str, relative_path: str) -> bytes:
        reads.append((prefix_id, relative_path))
        return b"unexpected"

    monkeypatch.setattr(manager.storage_manager, "read_bytes", record_read)
    with pytest.raises(ValidationError, match="mutually exclusive"):
        dataset.generate_embed(field="embedding", source=view, branch="experiment")
    assert reads == []


def test_generate_embed_preserves_existing_values_when_inference_fails(tmp_path: Path) -> None:
    manager, repo, dataset, view, objects = setup_dataset(tmp_path)
    field = repo.schema.add_vector(name="embedding", model_id="clip", distance="cosine")
    dataset.generate_embed(field="embedding")
    before = {item.asset_id: field.get(asset_id=item.asset_id) for item in objects}
    runtime = manager.model_manager._runtimes["clip"]  # pyright: ignore[reportPrivateUsage]
    assert isinstance(runtime, Runtime)
    runtime.fail = True

    with pytest.raises(RuntimeError, match="injected"):
        dataset.generate_embed(field="embedding", overwrite=True)

    assert {item.asset_id: field.get(asset_id=item.asset_id) for item in objects} == before
    assert dataset.open_branch().snapshot_id == view.snapshot_id


def test_generate_embed_rejects_replaced_content_before_publish(tmp_path: Path) -> None:
    manager, repo, dataset, _, objects = setup_dataset(tmp_path)
    repo.schema.add_vector(name="embedding", model_id="clip", distance="cosine")
    stored = objects[0]
    prefix = manager.storage_manager.get_prefix(prefix_id=stored.storage_prefix_id)
    (Path(prefix.root) / stored.relative_path).write_bytes(b"tampered")

    with pytest.raises(ContentIntegrityError):
        dataset.generate_embed(field="embedding")

    assert all(repo.schema.get_vector(name="embedding").get(asset_id=item.asset_id) is None for item in objects)


def test_repo_vector_is_shared_by_same_asset_across_datasets(tmp_path: Path) -> None:
    _, repo, dataset, view, objects = setup_dataset(tmp_path)
    repo.schema.add_vector(name="embedding", model_id="clip", distance="cosine")
    dataset.generate_embed(field="embedding")
    other = repo.create_dataset(name="Other")
    other_view = other.commit(branch="main", base=other.open_branch(), frame=view.scan()).view

    shared = other_view.scan(fields=["asset_id", "embedding"])

    assert set(shared["asset_id"]) == {item.asset_id for item in objects}
    assert shared["embedding"].notna().all()
