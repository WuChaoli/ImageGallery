from pathlib import Path

import pandas as pd

from image_gallery.cleaning.result import CleanerResult
from image_gallery.cleaning.state import CleanerRunState, JsonRunStateStore


def test_result_export_table_writes_copy(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    tables_dir = run_dir / "tables"
    tables_dir.mkdir(parents=True)
    pd.DataFrame({"image_id": ["img-1"], "decode_ok": [True]}).to_parquet(
        tables_dir / "parameter_table.parquet",
        index=False,
    )
    result = CleanerResult(run_id="run-1", cache_root=tmp_path)

    output = result.export_table("parameter", tmp_path / "parameter_copy.parquet")

    assert output == tmp_path / "parameter_copy.parquet"
    assert pd.read_parquet(output)["image_id"].tolist() == ["img-1"]


def test_result_does_not_expose_work_dir() -> None:
    result = CleanerResult(run_id="run-1", cache_root=Path("/tmp/run"))

    assert not hasattr(result, "cache_root")
    assert not hasattr(result, "work_dir")


def test_cleanup_does_not_remove_fallback_candidate_when_run_id_mismatch(tmp_path: Path) -> None:
    (tmp_path / "run-1" / "tables").mkdir(parents=True)
    (tmp_path / "run-other" / "tables").mkdir(parents=True)
    (tmp_path / "run-1" / "tables" / "parameter_table.parquet").write_text("")
    protected = tmp_path / "run-other"

    result = CleanerResult(run_id="run-missing", cache_root=tmp_path)
    result.cleanup()

    assert not (tmp_path / "run-missing").exists()
    assert protected.exists()
    assert (protected / "tables").exists()


def test_result_export_full_returns_expected_rows(tmp_path: Path) -> None:
    tables_dir = tmp_path / "run-1" / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "image_id": ["img-1", "img-2"],
            "image_uri": ["/tmp/one.png", "/tmp/two.png"],
            "decode_action": ["keep", "drop"],
            "final_action": ["keep", "drop"],
            "final_reason": ["", ""],
            "triggered_operator_names": ["", ""],
        }
    ).to_parquet(tables_dir / "evaluation_table.parquet", index=False)
    pd.DataFrame(
        {"image_id": ["img-1", "img-2"], "decode_ok": [True, False], "decode_error": ["", ""]}
    ).to_parquet(tables_dir / "parameter_table.parquet", index=False)

    result = CleanerResult(run_id="run-1", cache_root=tmp_path)
    output = result.export("full", tmp_path / "full.parquet")

    assert output.to_frame()["image_id"].tolist() == ["img-1", "img-2"]


def test_result_explain_removes_relation_paths_from_public_output(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    tables_dir = run_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"image_id": ["img-1"], "image_uri": ["/tmp/one.png"]}).to_parquet(
        tables_dir / "parameter_table.parquet",
        index=False,
    )
    pd.DataFrame(
        {
            "image_id": ["img-1"],
            "image_uri": ["/tmp/one.png"],
            "final_action": ["keep"],
            "final_reason": [""],
            "triggered_operator_names": [""],
        }
    ).to_parquet(tables_dir / "evaluation_table.parquet", index=False)
    run_state = CleanerRunState(
        run_id="run-1",
        dataset_fingerprint="fp",
        cleaner_type="basic",
        enabled_operator_configs=[],
        operator_config_hashes={},
        parameter_config_hashes={},
        parameter_table_path=str(tables_dir / "parameter_table.parquet"),
        evaluation_table_path=str(tables_dir / "evaluation_table.parquet"),
        operator_outputs_path=str(run_dir / "operator_outputs.yaml"),
        parameter_manifest_path=str(run_dir / "parameter_manifest.json"),
        relation_paths={"dup_pairs": str(tables_dir / "relation.parquet")},
        artifact_paths={},
        started_at="",
        finished_at="",
        status="succeeded",
        operator_states=[],
    )
    JsonRunStateStore().save(run_state, run_dir / "state.json")

    result = CleanerResult(run_id="run-1", cache_root=tmp_path)
    explanation = result.explain("img-1")

    assert "relation_paths" not in explanation
    assert explanation["relation_names"] == ["dup_pairs"]
