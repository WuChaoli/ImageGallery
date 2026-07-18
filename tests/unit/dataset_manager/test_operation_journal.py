from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, insert, select
from sqlalchemy.engine import Engine

from image_gallery.dataset_manager._operation_journal import OperationJournal
from image_gallery.dataset_manager.control import metadata, operation_phases, operations, repos


@pytest.fixture
def control_engine() -> Iterator[Engine]:  # pyright: ignore[reportUnknownParameterType]
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"control": None, "vectors": None})
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            insert(repos).values(repo_id="repo-1", name="Vision", name_key="vision", namespace="r_vision")
        )
    try:
        yield engine
    finally:
        engine.dispose()


def test_operation_journal_persists_intent_phase_and_final_status(control_engine: Engine) -> None:  # pyright: ignore[reportUnknownParameterType]
    events: list[tuple[str, str]] = []
    journal = OperationJournal(
        control_engine, operation_hook=lambda operation_id, phase: events.append((operation_id, phase))
    )

    operation_id = journal.start(
        kind="create_dataset",
        repo_id="repo-1",
        dataset_id="dataset-1",
        intent={"name": "Raw"},
    )
    journal.update_intent(operation_id=operation_id, values={"table_identifier": "r_vision.d_raw"})
    journal.record_phase(operation_id=operation_id, phase="table_created", details={"snapshot_id": 7})

    pending = journal.pending()
    assert [(item.operation_id, item.kind, item.intent) for item in pending] == [
        (
            operation_id,
            "create_dataset",
            {"name": "Raw", "table_identifier": "r_vision.d_raw"},
        )
    ]
    assert journal.has_active_dataset_operation(dataset_id="dataset-1") is True
    assert events == [(operation_id, "table_created")]

    with control_engine.connect() as connection:
        phase = (
            connection.execute(select(operation_phases).where(operation_phases.c.operation_id == operation_id))
            .mappings()
            .one()
        )
    assert phase["phase"] == "table_created"
    assert phase["status"] == "complete"
    assert phase["details"] == {"snapshot_id": 7}

    journal.finalize(operation_id=operation_id)

    assert journal.pending() == []
    assert journal.has_active_dataset_operation(dataset_id="dataset-1") is False
    with control_engine.connect() as connection:
        status = connection.execute(
            select(operations.c.status).where(operations.c.operation_id == operation_id)
        ).scalar_one()
    assert status == "finalized"


def test_operation_journal_marks_operation_failed_without_losing_intent(control_engine: Engine) -> None:  # pyright: ignore[reportUnknownParameterType]
    journal = OperationJournal(control_engine)
    operation_id = journal.start(
        kind="commit",
        repo_id="repo-1",
        dataset_id="dataset-1",
        intent={"branch": "main"},
    )

    journal.fail(operation_id=operation_id)

    with control_engine.connect() as connection:
        row = connection.execute(select(operations).where(operations.c.operation_id == operation_id)).mappings().one()
    assert row["status"] == "failed"
    assert row["intent"] == {"branch": "main"}
    assert journal.pending() == []
