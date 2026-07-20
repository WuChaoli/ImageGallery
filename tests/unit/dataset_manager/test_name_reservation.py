from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import create_engine, insert, select
from sqlalchemy.engine import Engine

from image_gallery.dataset_manager import NameConflictError, ValidationError
from image_gallery.dataset_manager._operation_journal import OperationJournal
from image_gallery.dataset_manager._repository_store import DatasetRecord, RepositoryStore
from image_gallery.dataset_manager.control import metadata, operations, repos
from image_gallery.storage_manager import StorageManager


@pytest.fixture
def reservation_engine(tmp_path: Path) -> Engine:  # pyright: ignore[reportUnknownParameterType]
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'control.db').as_posix()}",
        connect_args={"check_same_thread": False},
    ).execution_options(schema_translate_map={"control": None, "vectors": None})
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            insert(repos).values(repo_id="repo-1", name="Vision", name_key="vision", namespace="r_vision")
        )
    try:
        yield engine
    finally:
        engine.dispose()


def _reserve(journal: OperationJournal, *, dataset_id: str, name: str = "Images") -> str:
    return journal.start_with_dataset_name_reservation(
        kind="materialize_dataset",
        repo_id="repo-1",
        dataset_id=dataset_id,
        dataset_name=name,
        intent={"target_dataset_id": dataset_id},
    )


def test_same_name_reservation_has_one_concurrent_winner(reservation_engine: Engine) -> None:  # pyright: ignore[reportUnknownParameterType]
    journal = OperationJournal(reservation_engine)

    def attempt(dataset_id: str) -> tuple[str, str]:
        try:
            return "winner", _reserve(journal, dataset_id=dataset_id, name=" Images ")
        except NameConflictError as exc:
            return "loser", str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ["dataset-1", "dataset-2"]))

    assert sorted(result[0] for result in results) == ["loser", "winner"]
    with reservation_engine.connect() as connection:
        stored_operations = connection.execute(select(operations)).mappings().all()
    assert len(stored_operations) == 1
    assert stored_operations[0]["status"] == "active"


def test_active_or_failed_reservation_requires_explicit_safe_release(reservation_engine: Engine) -> None:  # pyright: ignore[reportUnknownParameterType]
    journal = OperationJournal(reservation_engine)
    operation_id = _reserve(journal, dataset_id="dataset-1")

    with pytest.raises(ValidationError, match="failed"):
        journal.release_failed_dataset_name_reservation(operation_id=operation_id)
    journal.fail(operation_id=operation_id)
    with pytest.raises(NameConflictError, match="images"):
        _reserve(journal, dataset_id="dataset-2", name="images")

    journal.release_failed_dataset_name_reservation(operation_id=operation_id)

    replacement = _reserve(journal, dataset_id="dataset-2", name="IMAGES")
    assert replacement != operation_id


def test_reserved_registration_is_consistent_atomic_and_idempotent(reservation_engine: Engine) -> None:  # pyright: ignore[reportUnknownParameterType]
    journal = OperationJournal(reservation_engine)
    store = RepositoryStore(reservation_engine, storage_manager=StorageManager())
    operation_id = _reserve(journal, dataset_id="dataset-1")
    record = DatasetRecord(
        repo_id="repo-1",
        dataset_id="dataset-1",
        name="Images",
        table_identifier="r_vision.d_images",
    )

    with pytest.raises(ValidationError, match="reservation"):
        store.register_reserved_dataset(operation_id=operation_id, record=record, name_key="other")
    with pytest.raises(ValidationError, match="reservation"):
        store.register_reserved_dataset(
            operation_id=operation_id,
            record=DatasetRecord(
                repo_id="repo-1",
                dataset_id="dataset-1",
                name="Other",
                table_identifier="r_vision.d_images",
            ),
            name_key="images",
        )

    store.register_reserved_dataset(operation_id=operation_id, record=record, name_key="images")
    store.register_reserved_dataset(operation_id=operation_id, record=record, name_key="images")

    assert store.get_dataset(repo_id="repo-1", dataset_id="dataset-1") == record
    assert journal.get_active(operation_id=operation_id) is None
    with pytest.raises(NameConflictError, match="images"):
        _reserve(journal, dataset_id="dataset-2", name="images")


def test_reserved_registration_rejects_wrong_target_identity(reservation_engine: Engine) -> None:  # pyright: ignore[reportUnknownParameterType]
    journal = OperationJournal(reservation_engine)
    store = RepositoryStore(reservation_engine, storage_manager=StorageManager())
    operation_id = _reserve(journal, dataset_id="dataset-1")

    with pytest.raises(ValidationError, match="reservation"):
        store.register_reserved_dataset(
            operation_id=operation_id,
            record=DatasetRecord(
                repo_id="repo-1",
                dataset_id="dataset-2",
                name="Images",
                table_identifier="r_vision.d_other",
            ),
            name_key="images",
        )

    assert journal.get_active(operation_id=operation_id) is not None
