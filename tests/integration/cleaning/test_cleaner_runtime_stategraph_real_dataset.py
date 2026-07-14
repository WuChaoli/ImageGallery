"""Cleaner Runtime StateGraph 的 sample_1000 真实数据验收测试。"""

from __future__ import annotations

import sqlite3
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from notebooks._helpers.cleaning_configs import get_cleaning_v3_non_semantic_all_operator_configs
from notebooks._helpers.datasets import (
    load_default_minio_sample_1000_dataset,
    load_default_minio_sample_1000_frame,
)

from image_gallery.cleaning import BasicCleaner


@pytest.fixture(scope="module")
def sample_1000_dataset():
    """加载默认 MinIO sample_1000 数据集，不可用时明确跳过。"""
    try:
        return load_default_minio_sample_1000_dataset()
    except Exception as exc:
        pytest.skip(f"sample_1000 real dataset unavailable: {exc}")


@pytest.fixture(scope="module")
def non_semantic_real_result(sample_1000_dataset):
    """执行一次真实非语义全量清洗，后续测试复用结果降低成本。"""
    events = []
    configs = get_cleaning_v3_non_semantic_all_operator_configs()
    result = (
        BasicCleaner(configs)
        .compile()
        .run(
            sample_1000_dataset,
            progress=events.append,
            label="sample-1000-stategraph-real",
            tags=["sample_1000", "stategraph", "non_semantic_all"],
        )
    )
    return result, events


def _expected_non_semantic_operator_names() -> list[str]:
    """返回非语义全量配置中的算子名称顺序。"""
    return [next(iter(item.keys())) for item in get_cleaning_v3_non_semantic_all_operator_configs()]


def test_sample_1000_real_dataset_contract(sample_1000_dataset) -> None:
    frame = load_default_minio_sample_1000_frame()
    assert len(frame) == 1000
    assert {"image_id", "image_uri"}.issubset(frame.columns)

    dataset_frame = sample_1000_dataset.to_frame()
    assert len(dataset_frame) == 1000
    assert dataset_frame["image_id"].is_unique
    assert sample_1000_dataset.fingerprint()


def test_non_semantic_all_compile_and_dry_run_on_sample_1000(sample_1000_dataset) -> None:
    execution = BasicCleaner(get_cleaning_v3_non_semantic_all_operator_configs()).compile()
    plan = execution.plan()
    dry_run = execution.dry_run(sample_1000_dataset)
    expected_operator_names = _expected_non_semantic_operator_names()

    assert dry_run.errors == []
    assert dry_run.selected_operators == expected_operator_names
    assert set(expected_operator_names).issubset(dry_run.preview_policies)
    assert "tables/parameter_table.parquet" in dry_run.estimated_artifacts
    assert "tables/evaluation_table.parquet" in dry_run.estimated_artifacts

    node_ids = set(plan["node_id"])
    assert "merge.final_action" in node_ids
    assert any(node_id.startswith("parameter.") for node_id in node_ids)
    for operator_name in expected_operator_names:
        assert f"evaluation.{operator_name}" in node_ids


def test_selector_compile_on_sample_1000_dry_run(sample_1000_dataset) -> None:
    execution = BasicCleaner(["QUALITY", "DUPLICATE"]).compile()
    dry_run = execution.dry_run(sample_1000_dataset)

    assert dry_run.errors == []
    assert {"blur", "brightness", "contrast", "exposure", "noise"}.issubset(dry_run.selected_operators)
    assert {"exact_duplicate", "perceptual_duplicate", "semantic_duplicate"}.issubset(dry_run.selected_operators)
    assert len(dry_run.selected_operators) == len(set(dry_run.selected_operators))


def test_non_semantic_real_run_status_events_and_tables(non_semantic_real_result) -> None:
    result, events = non_semantic_real_result

    assert result.status() == "completed"
    assert any(event.event_type == "run_started" for event in events)
    assert any(event.event_type == "run_completed" for event in events)
    assert any(event.node_id == "merge.final_action" for event in events)

    export_dir = result._run_dir() / "_test_exports" / "tables"
    parameter_path = result.export_table("parameter", export_dir / "parameter.parquet")
    evaluation_path = result.export_table("evaluation", export_dir / "evaluation.parquet")
    parameter_table = pd.read_parquet(parameter_path)
    evaluation_table = pd.read_parquet(evaluation_path)

    assert len(parameter_table) == 1000
    assert len(evaluation_table) == 1000
    assert "final_action" in evaluation_table.columns
    assert set(evaluation_table["final_action"]).issubset({"keep", "drop", "review"})


def test_non_semantic_real_run_operator_outputs(non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    expected_operator_names = _expected_non_semantic_operator_names()

    state = result.state()
    assert list(state["operator_name"]) == expected_operator_names

    for operator_name in expected_operator_names:
        operator_frame = result.result(operator_name)
        assert len(operator_frame) == 1000
        action_columns = [column for column in operator_frame.columns if column.endswith("_action")]
        assert action_columns, operator_name


def test_real_result_exports_action_partitions(non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    export_dir = result._run_dir() / "_test_exports" / "partitions"

    full = result.export("full", export_dir / "full.parquet").to_frame()
    clean = result.export("clean", export_dir / "clean.parquet").to_frame()
    review = result.export("review", export_dir / "review.parquet").to_frame()
    dropped = result.export("dropped", export_dir / "dropped.parquet").to_frame()

    assert len(full) == 1000
    assert len(clean) == int((full["final_action"] == "keep").sum())
    assert len(review) == int((full["final_action"] == "review").sum())
    assert len(dropped) == int((full["final_action"] == "drop").sum())
    assert len(full) == len(clean) + len(review) + len(dropped)


def test_real_result_exports_manifests_and_debug_bundle(non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    export_dir = result._run_dir() / "_test_exports" / "debug"

    execution_plan = result.export_manifest("execution_plan", export_dir / "execution_plan.json")
    artifacts = result.export_manifest("artifacts", export_dir / "artifacts.json")
    bundle = result.export_debug_bundle(export_dir / "debug-cleaning-run.zip")

    assert "merge.final_action" in execution_plan.read_text(encoding="utf-8")
    assert artifacts.read_text(encoding="utf-8").startswith("{")
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
    assert "tables/parameter_table.parquet" in names
    assert "tables/evaluation_table.parquet" in names
    assert "state.json" in names


def test_real_result_preview_html_policy_and_overrides(non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    preview_dir = result._run_dir() / "_test_exports" / "previews"

    overall = result.preview_html(preview_dir / "overall.html")
    blur = result.preview_html(preview_dir / "blur.html", operator_name="blur")
    clean = result.preview_html(
        preview_dir / "clean.html",
        actions="clean",
        max_rows=30,
        columns_per_row=5,
    )

    rendered_html = []
    for path in (overall, blur, clean):
        html = path.read_text(encoding="utf-8")
        rendered_html.append(html)
        assert "<html" in html.lower()
        assert "<section" in html.lower()
    assert any("<img" in html.lower() for html in rendered_html)


def test_real_result_explain_contains_parameters_and_outputs(non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    export_path = result._run_dir() / "_test_exports" / "explain" / "full.parquet"
    full = result.export("full", export_path).to_frame()
    image_id = str(full.iloc[0]["image_id"])

    explanation = result.explain(image_id)

    assert explanation["image_id"] == image_id
    assert explanation["final_action"] in {"keep", "drop", "review"}
    assert "parameters" in explanation
    assert "operator_outputs" in explanation
    assert "relation_names" in explanation


def test_real_run_sqlite_state_contains_graph_and_events(non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    database_path = result._run_dir() / "run_state.sqlite"
    assert database_path.exists()

    connection = sqlite3.connect(database_path)
    try:
        run_status = connection.execute(
            "SELECT status FROM cleaning_run WHERE run_id = ?",
            (result.run_id,),
        ).fetchone()[0]
        node_count = connection.execute("SELECT COUNT(*) FROM graph_node").fetchone()[0]
        completed_count = connection.execute(
            "SELECT COUNT(*) FROM graph_node WHERE status = 'completed'",
        ).fetchone()[0]
        event_count = connection.execute("SELECT COUNT(*) FROM run_event").fetchone()[0]
    finally:
        connection.close()

    assert run_status == "completed"
    assert node_count > 0
    assert completed_count == node_count
    assert event_count > 0


def test_real_completed_resume_returns_same_run(sample_1000_dataset, non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    execution = BasicCleaner(get_cleaning_v3_non_semantic_all_operator_configs()).compile()

    resumed = execution.resume(dataset=sample_1000_dataset, result=result)

    assert resumed.run_id == result.run_id
    assert resumed.status() == "completed"


def test_real_toml_recipe_runs_on_sample_1000(sample_1000_dataset, tmp_path: Path) -> None:
    recipe_path = tmp_path / "cleaner_runtime_non_semantic.toml"
    recipe_path.write_text(
        "\n".join(
            [
                "[operators.blur]",
                "min_score = 0.0",
                'action = "review"',
                "",
                "[operators.exact_duplicate]",
                'action = "drop"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = BasicCleaner.from_toml(recipe_path).run(sample_1000_dataset, label="sample-1000-toml")

    assert result.status() == "completed"
    assert len(result.export("full", tmp_path / "full.parquet").to_frame()) == 1000
