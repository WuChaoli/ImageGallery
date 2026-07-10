from pathlib import Path

from image_gallery.cleaning.runtime_state import RunRecord, SQLiteRunStateStore


def _columns(store: SQLiteRunStateStore, table_name: str) -> set[str]:
    rows = store._connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def test_sqlite_store_initializes_run_and_events(tmp_path: Path) -> None:
    store = SQLiteRunStateStore.initialize(
        tmp_path,
        RunRecord(
            run_id="run-1",
            cleaner_type="basic",
            status="running",
            dataset_fingerprint="fp",
            plan_hash="plan",
            label="smoke",
            tags=["sample"],
            sample_size=None,
            sample_rule=None,
        ),
    )

    store.record_event("run_started", message="started", payload={"phase": 1})
    loaded = store.load_run("run-1")
    events = store.list_events("run-1")

    assert loaded.label == "smoke"
    assert loaded.tags == ["sample"]
    assert events[0].event_type == "run_started"
    assert events[0].run_id == "run-1"


def test_state_schema_records_cache_artifact_status_and_batch_ranges(tmp_path: Path) -> None:
    """SQLite schema 应覆盖设计稿里的 run/artifact/batch 状态字段。"""
    store = SQLiteRunStateStore.initialize(
        tmp_path,
        RunRecord(
            run_id="run-1",
            cleaner_type="basic",
            status="running",
            dataset_fingerprint="fp",
            plan_hash="plan",
            label="smoke",
            tags=[],
            sample_size=None,
            sample_rule=None,
        ),
    )

    assert {"cache_root", "started_at", "updated_at", "finished_at"} <= _columns(store, "cleaning_run")
    assert {"uri", "status", "manifest_uri"} <= _columns(store, "artifact")
    assert {"input_start", "input_end", "error_count", "attempt_count", "artifact_id"} <= _columns(store, "batch_run")
