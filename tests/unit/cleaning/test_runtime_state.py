from pathlib import Path

from image_gallery.cleaning.runtime_state import RunRecord, SQLiteRunStateStore


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
