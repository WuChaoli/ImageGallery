import json
from pathlib import Path

from image_gallery.cleaning.state import CleanerRunState, JsonRunStateStore, OperatorRunState, build_state_frame


def _state() -> CleanerRunState:
    return CleanerRunState(
        run_id="run-1",
        dataset_fingerprint="fp",
        cleaner_type="basic",
        enabled_operator_configs=[{"quality.demo_check": {"action": "review"}}],
        operator_config_hashes={"quality.demo_check": "abc"},
        parameter_config_hashes={"demo_score": "default"},
        parameter_table_path="parameter_table.parquet",
        evaluation_table_path="evaluation_table.parquet",
        operator_outputs_path="operator_outputs.yaml",
        parameter_manifest_path="parameter_manifest.json",
        relation_paths={},
        artifact_paths={"quality.demo_check": "artifacts/demo"},
        started_at="2026-07-06T00:00:00+00:00",
        finished_at="2026-07-06T00:00:01+00:00",
        status="completed",
        operator_states=[
            OperatorRunState(
                operator_name="quality.demo_check",
                config_hash="abc",
                status="completed",
                parameter_columns=["demo_score"],
                evaluation_columns=["demo_action", "demo_reason"],
                processed_count=1,
                skipped_count=0,
                failed_count=0,
            )
        ],
    )


def test_json_run_state_store_round_trips_state(tmp_path: Path) -> None:
    store = JsonRunStateStore()
    path = tmp_path / "state.json"

    store.save(_state(), path)
    loaded = store.load(path)

    assert loaded == _state()
    assert not (tmp_path / "state.json.tmp").exists()


def test_build_state_frame_returns_operator_matrix() -> None:
    frame = build_state_frame(_state())

    assert frame.to_dict(orient="records") == [
        {
            "operator_name": "quality.demo_check",
            "status": "completed",
            "processed_count": 1,
            "skipped_count": 0,
            "failed_count": 0,
            "message": None,
        }
    ]


def test_state_store_loads_legacy_payload_with_new_defaults(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "dataset_fingerprint": "fp",
                "cleaner_type": "basic",
                "enabled_operator_configs": [],
                "operator_config_hashes": {},
                "parameter_table_path": "parameter_table.parquet",
                "evaluation_table_path": "evaluation_table.parquet",
                "operator_outputs_path": "operator_outputs.yaml",
                "artifact_paths": {},
                "status": "completed",
                "operator_states": [],
            }
        ),
        encoding="utf-8",
    )

    state = JsonRunStateStore().load(path)

    assert state.parameter_config_hashes == {}
    assert state.parameter_manifest_path == ""
    assert state.relation_paths == {}
    assert state.started_at == ""
    assert state.finished_at == ""
