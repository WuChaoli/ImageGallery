import threading
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import pytest
from pyiceberg.types import ListType, NestedField, StructType

from image_gallery.dataset_manager import (
    ColumnSpec,
    DatasetManager,
    ListFieldType,
    MaterializeResult,
    NameConflictError,
    PrimitiveFieldType,
    StructField,
    StructFieldType,
    ValidationError,
)
from image_gallery.model_manager import ModelDefinition
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


def _nested_field_ids(field: NestedField) -> list[int]:  # pyright: ignore[reportUnknownParameterType]
    result = [field.field_id]
    field_type = field.field_type
    if isinstance(field_type, ListType):
        result.append(field_type.element_id)
        if isinstance(field_type.element_type, ListType | StructType):
            nested = NestedField(field_type.element_id, "element", field_type.element_type)
            result.extend(_nested_field_ids(nested)[1:])
    elif isinstance(field_type, StructType):
        for child in field_type.fields:
            result.extend(_nested_field_ids(child))
    return result


def test_materialize_freezes_current_schema_and_complete_frame(tmp_path: Path) -> None:
    storage, manager, repo, source, row = _setup_source(tmp_path)
    base = source.schema.add_column(branch="main", base=source.open_branch(), name="split", field_type="string")
    row["split"] = "train"
    fixed = source.commit(branch="main", base=base, frame=pd.DataFrame([row])).view
    source.schema.add_column(branch="main", base=source.open_branch(), name="score", field_type="long")

    result = repo.materialize_dataset(
        source=fixed,
        name="Clean",
        frame=fixed.scan(),
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


def test_materialize_rejects_vector_field_name_collision(tmp_path: Path) -> None:
    _, manager, repo, source, row = _setup_source(tmp_path)
    fixed = source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row])).view
    manager.model_manager.register(
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
    repo.schema.add_vector(name=" Embedding ", model_id="clip", distance="cosine")

    with pytest.raises(ValidationError, match="VectorField"):
        repo.materialize_dataset(
            source=fixed,
            name="Clean",
            frame=fixed.scan(),
            schema_additions=(ColumnSpec("embedding", PrimitiveFieldType("long")),),
        )


@pytest.mark.parametrize("columns", [[], ["asset_id"], ["asset_id", "unknown"]])
def test_materialize_empty_frame_requires_exact_target_schema(tmp_path: Path, columns: list[str]) -> None:
    _, _, repo, source, row = _setup_source(tmp_path)
    fixed = source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row])).view

    with pytest.raises(ValidationError, match="Empty materialize frame"):
        repo.materialize_dataset(source=fixed, name="Empty", frame=pd.DataFrame(columns=columns))


def test_materialize_accepts_sequence_schema_additions(tmp_path: Path) -> None:
    _, _, repo, source, row = _setup_source(tmp_path)
    fixed = source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row])).view
    additions: Sequence[ColumnSpec] = [ColumnSpec("quality", "long")]

    result = repo.materialize_dataset(
        source=fixed,
        name="Clean",
        frame=fixed.scan(),
        schema_additions=additions,
    )

    assert result.dataset.schema.get_column(name="quality") == additions[0]


def test_materialize_round_trips_nullable_and_deeply_nested_columns(tmp_path: Path) -> None:
    _, manager, repo, source, row = _setup_source(tmp_path)
    additions = (
        ColumnSpec("nullable_items", ListFieldType("string")),
        ColumnSpec(
            "all_null_nested",
            StructFieldType(
                (
                    StructField("values", ListFieldType("long")),
                    StructField("note", "string"),
                )
            ),
        ),
        ColumnSpec(
            "matrix",
            ListFieldType(ListFieldType("long", element_required=False), element_required=False),
        ),
    )
    nested_row = {
        **row,
        "nullable_items": None,
        "all_null_nested": {"values": None, "note": None},
        "matrix": [None, [], [1, None]],
    }
    fixed = source.commit(
        branch="main",
        base=source.open_branch(),
        frame=pd.DataFrame([nested_row]),
        schema_additions=additions,
    ).view

    result = repo.materialize_dataset(source=fixed, name="Nested", frame=fixed.scan())

    assert result.view.scan().to_dict(orient="records") == [nested_row]
    for addition in additions:
        assert result.dataset.schema.get_column(name=addition.name) == addition
    target_table = manager.catalog.load_table(result.dataset.table_identifier)
    field_ids = [field_id for field in target_table.schema().fields for field_id in _nested_field_ids(field)]
    assert len(field_ids) == len(set(field_ids))


def test_materialize_normalizes_display_name_and_reopens_with_whitespace(tmp_path: Path) -> None:
    _, _, repo, source, row = _setup_source(tmp_path)
    fixed = source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row])).view

    result = repo.materialize_dataset(source=fixed, name=" Clean ", frame=fixed.scan())

    assert result.dataset.name == "Clean"
    assert repo.open_dataset(name=" clean ").dataset_id == result.dataset.dataset_id
    assert [dataset.name for dataset in repo.list_datasets()] == ["Clean", "Source"]


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


@pytest.mark.parametrize(
    "interrupted_phase",
    ["materialize_table_created", "materialize_schema_created", "materialize_snapshot_created"],
)
def test_materialize_recovers_from_each_catalog_phase(tmp_path: Path, interrupted_phase: str) -> None:
    storage, _, repo, source, row = _setup_source(tmp_path)
    source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row]))

    def interrupt(_operation_id: str, phase: str) -> None:
        if phase == interrupted_phase:
            raise RuntimeError(interrupted_phase)

    interrupted = DatasetManager.local(
        root=tmp_path / "backend",
        storage_manager=storage,
        operation_hook=interrupt,
    )
    interrupted_repo = interrupted.open_repo(name=repo.name)
    interrupted_source = interrupted_repo.open_dataset(name=source.name).open_branch()
    with pytest.raises(RuntimeError, match=interrupted_phase):
        interrupted_repo.materialize_dataset(
            source=interrupted_source,
            name="Clean",
            frame=interrupted_source.scan(),
            schema_additions=(ColumnSpec("quality", "long"),),
        )
    assert [dataset.name for dataset in interrupted_repo.list_datasets()] == ["Source"]

    recovered = DatasetManager.local(root=tmp_path / "backend", storage_manager=storage)
    assert recovered.recover_operations() == 1
    clean = recovered.open_repo(name="Vision").open_dataset(name="Clean")
    assert clean.open_branch().scan().to_dict(orient="records") == [{**row, "quality": None}]


def test_two_public_materialize_calls_have_one_reservation_winner(tmp_path: Path) -> None:
    entered = threading.Event()
    release = threading.Event()

    def pause_after_table(_operation_id: str, phase: str) -> None:
        if phase == "materialize_table_created":
            entered.set()
            assert release.wait(timeout=10)

    storage = StorageManager()
    manager = DatasetManager.local(
        root=tmp_path / "backend",
        storage_manager=storage,
        operation_hook=pause_after_table,
    )
    prefix = storage.register_file_prefix(name="images", root=tmp_path / "images")
    repo = manager.create_repo(name="Vision")
    repo.bind_storage_prefix(prefix_id=prefix.prefix_id)
    source = repo.create_dataset(name="Source")
    stored = storage.write_managed(prefix_id=prefix.prefix_id, data=b"image")
    row = {
        "asset_id": stored.asset_id,
        "storage_prefix_id": stored.storage_prefix_id,
        "relative_path": stored.relative_path,
        "source_uri": None,
        "tag_ids": [],
    }
    fixed = source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row])).view
    frame = fixed.scan()
    winner_outcomes: list[object] = []
    loser_outcomes: list[object] = []
    loser_done = threading.Event()

    def materialize_winner() -> None:
        try:
            winner_outcomes.append(repo.materialize_dataset(source=fixed, name="Clean", frame=frame))
        except Exception as exc:  # noqa: BLE001
            winner_outcomes.append(exc)

    def materialize_loser() -> None:
        try:
            loser_outcomes.append(repo.materialize_dataset(source=fixed, name=" clean ", frame=frame))
        except Exception as exc:  # noqa: BLE001
            loser_outcomes.append(exc)
        finally:
            loser_done.set()

    worker = threading.Thread(target=materialize_winner)
    worker.start()
    assert entered.wait(timeout=10)
    tables_before = set(manager.catalog.list_tables(repo.namespace))
    loser = threading.Thread(target=materialize_loser)
    loser.start()
    assert not loser_done.wait(timeout=0.2)
    assert set(manager.catalog.list_tables(repo.namespace)) == tables_before
    release.set()
    worker.join(timeout=10)
    loser.join(timeout=10)

    assert not worker.is_alive()
    assert not loser.is_alive()
    assert len(winner_outcomes) == 1
    assert isinstance(winner_outcomes[0], MaterializeResult)
    assert len(loser_outcomes) == 1
    assert isinstance(loser_outcomes[0], NameConflictError)


@pytest.mark.parametrize("competitor", ["create", "clone"])
def test_create_and_clone_cannot_bypass_materialize_reservation(tmp_path: Path, competitor: str) -> None:
    storage, _, repo, source, row = _setup_source(tmp_path)
    source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row]))

    def interrupt(_operation_id: str, phase: str) -> None:
        if phase == "materialize_table_created":
            raise RuntimeError("interrupted")

    interrupted = DatasetManager.local(
        root=tmp_path / "backend",
        storage_manager=storage,
        operation_hook=interrupt,
    )
    interrupted_repo = interrupted.open_repo(name=repo.name)
    interrupted_source = interrupted_repo.open_dataset(name=source.name).open_branch()
    with pytest.raises(RuntimeError, match="interrupted"):
        interrupted_repo.materialize_dataset(
            source=interrupted_source,
            name="Reserved",
            frame=interrupted_source.scan(),
        )
    tables_before = set(interrupted.catalog.list_tables(interrupted_repo.namespace))

    def compete() -> None:
        if competitor == "create":
            interrupted_repo.create_dataset(name=" reserved ")
        else:
            interrupted_repo.clone_dataset(source=interrupted_source, name=" reserved ")

    with pytest.raises(NameConflictError):
        compete()

    assert set(interrupted.catalog.list_tables(interrupted_repo.namespace)) == tables_before


def test_materialize_rejects_invalid_source_before_catalog_side_effect(tmp_path: Path) -> None:
    _, manager, first, source, row = _setup_source(tmp_path)
    fixed = source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row])).view
    second = manager.create_repo(name="Other")

    with pytest.raises(ValidationError):
        second.materialize_dataset(source=fixed, name="Cross", frame=fixed.scan())
    with pytest.raises(ValidationError):
        first.materialize_dataset(source=source.open_branch(), name="Bad", frame=pd.DataFrame([{"asset_id": "bad"}]))

    assert not any(identifier[1].startswith("d_") for identifier in manager.catalog.list_tables(second.namespace))


def test_materialize_rejects_asset_location_not_owned_by_source_view_before_catalog_side_effect(
    tmp_path: Path,
) -> None:
    storage, manager, repo, source, row = _setup_source(tmp_path)
    fixed = source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row])).view
    alternate_prefix = storage.register_file_prefix(name="alternate", root=tmp_path / "alternate")
    repo.bind_storage_prefix(prefix_id=alternate_prefix.prefix_id)
    alternate = storage.write_managed(prefix_id=alternate_prefix.prefix_id, data=b"image")
    assert alternate.asset_id == row["asset_id"]
    frame = fixed.scan()
    frame.loc[0, "storage_prefix_id"] = alternate.storage_prefix_id
    frame.loc[0, "relative_path"] = alternate.relative_path
    tables_before = set(manager.catalog.list_tables(repo.namespace))

    with pytest.raises(ValidationError):
        repo.materialize_dataset(source=fixed, name="Invalid location", frame=frame)

    assert set(manager.catalog.list_tables(repo.namespace)) == tables_before
    assert manager.recover_operations() == 0


def test_materialize_rejects_duplicate_frame_columns_before_catalog_side_effect(tmp_path: Path) -> None:
    _, manager, repo, source, row = _setup_source(tmp_path)
    fixed = source.commit(branch="main", base=source.open_branch(), frame=pd.DataFrame([row])).view
    frame = fixed.scan()
    frame = pd.concat([frame, frame[["relative_path"]]], axis="columns")
    tables_before = set(manager.catalog.list_tables(repo.namespace))

    with pytest.raises(ValidationError, match="duplicate"):
        repo.materialize_dataset(source=fixed, name="Duplicate columns", frame=frame)

    assert set(manager.catalog.list_tables(repo.namespace)) == tables_before
    assert manager.recover_operations() == 0
