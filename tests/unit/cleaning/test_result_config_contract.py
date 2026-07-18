import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest
import yaml

from image_gallery.cleaning.recipe import CleanerRecipe
from image_gallery.cleaning.result import CleanerResult
from image_gallery.cleaning.toml_config import CleanerConfig, build_cleaner_toml_template


def _write_result_tables(run_dir: Path) -> None:
    tables_dir = run_dir / "tables"
    tables_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "image_id": ["img-review", "img-drop", "img-keep"],
            "image_uri": ["review.png", "drop.png", "keep.png"],
        }
    ).to_parquet(tables_dir / "parameter_table.parquet", index=False)
    pd.DataFrame(
        {
            "image_id": ["img-review", "img-drop", "img-keep"],
            "image_uri": ["review.png", "drop.png", "keep.png"],
            "final_action": ["keep", "keep", "keep"],
            "final_reason": ["", "", ""],
            "triggered_operator_names": ["demo", "demo", ""],
            "demo_action": ["review", "drop", "keep"],
            "demo_reason": ["reviewed", "dropped", ""],
            "score": [0.6, 0.1, 0.9],
        }
    ).to_parquet(tables_dir / "evaluation_table.parquet", index=False)


def test_result_status_defaults_to_running_for_missing_database_or_record(tmp_path: Path) -> None:
    result = CleanerResult("run-missing", tmp_path)
    assert result.status() == "running"

    run_dir = tmp_path / "run-missing"
    run_dir.mkdir()
    with sqlite3.connect(run_dir / "run_state.sqlite") as connection:
        connection.execute("CREATE TABLE cleaning_run (run_id TEXT, status TEXT)")
        connection.execute("INSERT INTO cleaning_run VALUES (?, ?)", ("another-run", "succeeded"))

    assert result.status() == "running"


def test_result_missing_manifests_keep_preview_and_result_readable(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    _write_result_tables(run_dir)
    result = CleanerResult("run-1", tmp_path)

    preview = result.preview(limit=2)

    assert preview.total_count == 3
    assert preview.clean_count == 3
    assert preview.sample_rows["image_id"].tolist() == ["img-review", "img-drop"]
    with pytest.raises(KeyError, match="unknown operator_name: demo"):
        result.result("demo")


def test_result_rejects_non_string_persisted_operator_output_columns(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    _write_result_tables(run_dir)
    manifests_dir = run_dir / "manifests"
    manifests_dir.mkdir()
    (manifests_dir / "operator_outputs.json").write_text(
        json.dumps({"demo": ["demo_action", 1]}),
        encoding="utf-8",
    )

    with pytest.raises(TypeError, match="invalid operator_outputs columns: 1"):
        CleanerResult("run-1", tmp_path).result("demo")


def test_result_operator_preview_preserves_action_filter_sort_and_limit(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-1"
    _write_result_tables(run_dir)
    manifests_dir = run_dir / "manifests"
    manifests_dir.mkdir()
    (manifests_dir / "operator_outputs.json").write_text(
        json.dumps({"demo": ["demo_action", "demo_reason", "score"]}),
        encoding="utf-8",
    )

    output = CleanerResult("run-1", tmp_path).preview_html(
        tmp_path / "preview.html",
        operator_name="demo",
        actions=("drop", "review"),
        sort_by=["score"],
        ascending=False,
        max_rows=1,
        caption_columns=["image_id", "demo_action"],
    )

    html = output.read_text(encoding="utf-8")
    assert "img-review" in html
    assert "img-drop" not in html
    assert "img-keep" not in html
    assert "demo_action: review" in html


def test_cleaner_toml_template_round_trips_selected_operators(tmp_path: Path) -> None:
    template = build_cleaner_toml_template(["blur", "exact_duplicate"])
    config_path = tmp_path / "cleaner.toml"
    config_path.write_text(template, encoding="utf-8")

    config = CleanerConfig.from_toml(config_path)

    assert config.selectors == ["blur", "exact_duplicate"]
    assert set(config.operator_configs) == {"blur", "exact_duplicate"}
    assert config.operator_policies == {}


def test_recipe_non_mapping_run_defaults_to_empty_mapping(tmp_path: Path) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    recipe_path.write_text(
        yaml.safe_dump({"run": ["invalid"], "operators": [{"use": "decode", "action": "drop"}]}),
        encoding="utf-8",
    )

    recipe = CleanerRecipe.from_yaml(recipe_path)

    assert recipe.run_defaults == {}
    assert recipe.compile_selectors() == [{"decode": {"action": "drop"}}]
