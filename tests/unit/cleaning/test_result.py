import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from image_gallery.cleaning.preview_policy import PreviewPolicy
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
    assert not hasattr(result, "dataset")
    assert not hasattr(result, "storage")


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
        operator_outputs_path=str(run_dir / "manifests" / "operator_outputs.json"),
        parameter_manifest_path=str(run_dir / "manifests" / "parameter_manifest.json"),
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


def test_result_export_relations_writes_copy(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    tables_dir = run_dir / "tables"
    relations_dir = run_dir / "relations"
    manifests_dir = run_dir / "manifests"
    tables_dir.mkdir(parents=True, exist_ok=True)
    relations_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"image_id": ["img-1"], "image_uri": ["/tmp/one.png"]}).to_parquet(
        tables_dir / "parameter_table.parquet",
        index=False,
    )
    pd.DataFrame({"image_id": ["img-1"], "image_uri": ["/tmp/one.png"], "final_action": ["keep"]}).to_parquet(
        tables_dir / "evaluation_table.parquet",
        index=False,
    )
    relation_path = relations_dir / "duplicate_pairs.parquet"
    pd.DataFrame(
        {
            "source_image_id": ["img-1"],
            "target_image_id": ["img-2"],
            "score": [1.0],
        }
    ).to_parquet(relation_path, index=False)
    JsonRunStateStore().save(
        CleanerRunState(
            run_id="run-1",
            dataset_fingerprint="fp",
            cleaner_type="basic",
            enabled_operator_configs=[],
            operator_config_hashes={},
            parameter_config_hashes={},
            parameter_table_path=str(tables_dir / "parameter_table.parquet"),
            evaluation_table_path=str(tables_dir / "evaluation_table.parquet"),
            operator_outputs_path=str(run_dir / "manifests" / "operator_outputs.json"),
            parameter_manifest_path=str(run_dir / "manifests" / "parameter_manifest.json"),
            relation_paths={"duplicate_pairs": str(relation_path)},
            artifact_paths={},
            started_at="",
            finished_at="",
            status="succeeded",
            operator_states=[],
        ),
        run_dir / "state.json",
    )
    result = CleanerResult(run_id="run-1", cache_root=tmp_path)

    output = result.export_relations("duplicate_pairs", tmp_path / "exported_relation.parquet")

    assert output == tmp_path / "exported_relation.parquet"
    assert pd.read_parquet(output)["target_image_id"].tolist() == ["img-2"]


def test_result_export_manifest_requires_named_manifest(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    manifests_dir = run_dir / "manifests"
    manifests_dir.mkdir(parents=True)
    (manifests_dir / "execution_plan.json").write_text('{"plan_hash": "abc"}', encoding="utf-8")
    (manifests_dir / "artifacts.json").write_text('{"artifacts": []}', encoding="utf-8")
    result = CleanerResult(run_id="run-1", cache_root=tmp_path)

    exported = result.export_manifest("execution_plan", tmp_path / "plan.json")

    assert json.loads(exported.read_text(encoding="utf-8")) == {"plan_hash": "abc"}
    with pytest.raises(ValueError, match="unsupported manifest kind"):
        result.export_manifest("parameter_manifest", tmp_path / "parameter.json")


def test_result_export_relations_writes_directory(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    tables_dir = run_dir / "tables"
    relations_dir = run_dir / "relations"
    manifests_dir = run_dir / "manifests"
    tables_dir.mkdir(parents=True, exist_ok=True)
    relations_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)
    relation_path = relations_dir / "duplicate_pairs.parquet"
    pd.DataFrame({"source_image_id": ["img-1"], "target_image_id": ["img-2"]}).to_parquet(
        relation_path,
        index=False,
    )
    JsonRunStateStore().save(
        CleanerRunState(
            run_id="run-1",
            dataset_fingerprint="fp",
            cleaner_type="basic",
            enabled_operator_configs=[],
            operator_config_hashes={},
            parameter_config_hashes={},
            parameter_table_path=str(tables_dir / "parameter_table.parquet"),
            evaluation_table_path=str(tables_dir / "evaluation_table.parquet"),
            operator_outputs_path=str(run_dir / "manifests" / "operator_outputs.json"),
            parameter_manifest_path=str(run_dir / "manifests" / "parameter_manifest.json"),
            relation_paths={"duplicate_pairs": str(relation_path)},
            artifact_paths={},
            started_at="",
            finished_at="",
            status="succeeded",
            operator_states=[],
        ),
        run_dir / "state.json",
    )
    result = CleanerResult(run_id="run-1", cache_root=tmp_path)

    output_path = result.export_relations("duplicate_pairs", tmp_path / "relations_export" / "duplicate_pairs.parquet")

    assert output_path == tmp_path / "relations_export" / "duplicate_pairs.parquet"
    assert pd.read_parquet(output_path)["target_image_id"].tolist() == ["img-2"]


def test_result_export_debug_bundle_writes_zip(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    tables_dir = run_dir / "tables"
    relations_dir = run_dir / "relations"
    manifests_dir = run_dir / "manifests"
    tables_dir.mkdir(parents=True, exist_ok=True)
    relations_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"image_id": ["img-1"], "image_uri": ["/tmp/one.png"]}).to_parquet(
        tables_dir / "parameter_table.parquet",
        index=False,
    )
    pd.DataFrame({"image_id": ["img-1"], "image_uri": ["/tmp/one.png"], "final_action": ["keep"]}).to_parquet(
        tables_dir / "evaluation_table.parquet",
        index=False,
    )
    (manifests_dir / "operator_outputs.json").write_text("{}", encoding="utf-8")
    (manifests_dir / "parameter_manifest.json").write_text("{}", encoding="utf-8")
    relation_path = relations_dir / "duplicate_pairs.parquet"
    pd.DataFrame({"source_image_id": ["img-1"], "target_image_id": ["img-2"]}).to_parquet(
        relation_path,
        index=False,
    )
    JsonRunStateStore().save(
        CleanerRunState(
            run_id="run-1",
            dataset_fingerprint="fp",
            cleaner_type="basic",
            enabled_operator_configs=[],
            operator_config_hashes={},
            parameter_config_hashes={},
            parameter_table_path=str(tables_dir / "parameter_table.parquet"),
            evaluation_table_path=str(tables_dir / "evaluation_table.parquet"),
            operator_outputs_path=str(run_dir / "manifests" / "operator_outputs.json"),
            parameter_manifest_path=str(run_dir / "manifests" / "parameter_manifest.json"),
            relation_paths={"duplicate_pairs": str(relation_path)},
            artifact_paths={},
            started_at="",
            finished_at="",
            status="succeeded",
            operator_states=[],
        ),
        run_dir / "state.json",
    )
    result = CleanerResult(run_id="run-1", cache_root=tmp_path)

    bundle_path = result.export_debug_bundle(tmp_path / "debug.zip")

    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
    assert "tables/parameter_table.parquet" in names
    assert "tables/evaluation_table.parquet" in names
    assert "state.json" in names
    assert "relations/duplicate_pairs.parquet" in names


def test_result_export_relations_rejects_unknown_relation(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    tables_dir = run_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    JsonRunStateStore().save(
        CleanerRunState(
            run_id="run-1",
            dataset_fingerprint="fp",
            cleaner_type="basic",
            enabled_operator_configs=[],
            operator_config_hashes={},
            parameter_config_hashes={},
            parameter_table_path=str(tables_dir / "parameter_table.parquet"),
            evaluation_table_path=str(tables_dir / "evaluation_table.parquet"),
            operator_outputs_path=str(run_dir / "manifests" / "operator_outputs.json"),
            parameter_manifest_path=str(run_dir / "manifests" / "parameter_manifest.json"),
            relation_paths={},
            artifact_paths={},
            started_at="",
            finished_at="",
            status="succeeded",
            operator_states=[],
        ),
        run_dir / "state.json",
    )
    result = CleanerResult(run_id="run-1", cache_root=tmp_path)

    try:
        result.export_relations("missing", tmp_path / "missing.parquet")
    except KeyError as error:
        assert "missing" in str(error)
    else:
        raise AssertionError("expected KeyError")


def test_result_preview_html_applies_configured_operator_preview_policy(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    tables_dir = run_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        {
            "image_id": ["img-one", "img-two"],
            "image_uri": ["/tmp/img-one.png", "/tmp/img-two.png"],
            "final_action": ["keep", "keep"],
            "final_reason": ["", ""],
            "triggered_operator_names": ["custom.custom_check", "custom.custom_check"],
            "custom_action": ["keep", "drop"],
            "custom_reason": ["", ""],
        }
    ).to_parquet(tables_dir / "evaluation_table.parquet", index=False)
    pd.DataFrame(
        {
            "image_id": ["img-one", "img-two"],
            "image_uri": ["/tmp/img-one.png", "/tmp/img-two.png"],
        }
    ).to_parquet(tables_dir / "parameter_table.parquet", index=False)
    manifests_dir = run_dir / "manifests"
    manifests_dir.mkdir()
    (manifests_dir / "operator_outputs.json").write_text(
        '{"custom.custom_check": ["custom_action", "custom_reason"]}',
        encoding="utf-8",
    )
    (manifests_dir / "parameter_manifest.json").write_text("{}", encoding="utf-8")

    result = CleanerResult(
        run_id="run-1",
        cache_root=tmp_path,
        operator_preview_policies={
            "custom.custom_check": PreviewPolicy(
                max_rows=1,
                columns_per_row=2,
                thumbnail_size=32,
            ),
        },
    )

    html = result.preview_html(
        tmp_path / "preview.html",
        operator_name="custom.custom_check",
    ).read_text(encoding="utf-8")

    assert "/tmp/img-one.png" in html
    assert "/tmp/img-two.png" not in html
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in html

    html_all = result.preview_html(
        tmp_path / "preview_all.html",
        operator_name="custom.custom_check",
        max_rows=2,
    ).read_text(encoding="utf-8")

    assert "/tmp/img-one.png" in html_all
    assert "/tmp/img-two.png" in html_all
