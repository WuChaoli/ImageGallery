from pathlib import Path

import pandas as pd
import pytest

from image_gallery.cleaning.context import build_run_paths
from image_gallery.cleaning.tables import (
    CleaningTables,
    initialize_evaluation_table,
    initialize_parameter_table,
    read_tables,
    update_evaluation_columns,
    update_operator_outputs,
    update_parameter_columns,
    write_tables,
)
from image_gallery.dataset import Dataset


def _dataset(tmp_path: Path, frame: pd.DataFrame) -> Dataset:
    return Dataset.write(frame, str(tmp_path / "raw.parquet"))


def test_initialize_parameter_table_requires_raw_identity_columns(tmp_path: Path) -> None:
    dataset = _dataset(
        tmp_path,
        pd.DataFrame(
            {
                "image_id": ["img-1"],
                "image_uri": ["platform://local/a.jpg"],
                "source_uri": ["file:///a.jpg"],
                "extra": ["ignored"],
            }
        ),
    )

    parameter_table = initialize_parameter_table(dataset)

    assert parameter_table.to_dict(orient="records") == [
        {
            "image_id": "img-1",
            "image_uri": "platform://local/a.jpg",
            "source_uri": "file:///a.jpg",
        }
    ]


def test_initialize_parameter_table_rejects_missing_required_columns(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path, pd.DataFrame({"image_uri": ["platform://local/a.jpg"]}))

    with pytest.raises(ValueError, match="image_id"):
        initialize_parameter_table(dataset)


def test_initialize_evaluation_table_starts_with_keep_defaults() -> None:
    parameter_table = pd.DataFrame({"image_id": ["img-1"], "image_uri": ["platform://local/a.jpg"]})

    evaluation_table = initialize_evaluation_table(parameter_table)

    assert evaluation_table.to_dict(orient="records") == [
        {
            "image_id": "img-1",
            "image_uri": "platform://local/a.jpg",
            "final_action": "keep",
            "final_reason": "",
            "triggered_operator_names": "",
        }
    ]


def test_update_parameter_columns_merges_by_image_id() -> None:
    parameter_table = pd.DataFrame({"image_id": ["img-1", "img-2"], "image_uri": ["a", "b"]})
    updates = pd.DataFrame({"image_id": ["img-1"], "demo_score": [0.5]})

    result = update_parameter_columns(parameter_table, updates)

    assert result.loc[result["image_id"] == "img-1", "demo_score"].item() == 0.5
    assert pd.isna(result.loc[result["image_id"] == "img-2", "demo_score"].item())


def test_update_evaluation_columns_rejects_foreign_output_columns() -> None:
    evaluation_table = pd.DataFrame({"image_id": ["img-1"], "image_uri": ["a"]})
    updates = pd.DataFrame({"image_id": ["img-1"], "demo_action": ["drop"], "other_action": ["review"]})

    with pytest.raises(ValueError, match="unexpected evaluation columns"):
        update_evaluation_columns(evaluation_table, updates, ["demo_action"])


def test_update_operator_outputs_rejects_column_ownership_conflicts() -> None:
    operator_outputs = {"quality.old_check": ["demo_action"]}

    with pytest.raises(ValueError, match="already owned"):
        update_operator_outputs(operator_outputs, "quality.new_check", ["demo_action"])


def test_write_and_read_tables_round_trip(tmp_path: Path) -> None:
    paths = build_run_paths(tmp_path / "run-1")
    tables = CleaningTables(
        parameter_table=pd.DataFrame({"image_id": ["img-1"], "image_uri": ["a"], "demo_score": [0.5]}),
        evaluation_table=pd.DataFrame({"image_id": ["img-1"], "image_uri": ["a"], "demo_action": ["drop"]}),
        operator_outputs={"quality.demo_check": ["demo_action"]},
        parameter_manifest={
            "demo_score": {
                "computer": "demo_computer",
                "stage": "image_batch",
                "config_hash": "abc123",
            }
        },
    )

    write_tables(tables, paths)
    loaded = read_tables(paths)

    pd.testing.assert_frame_equal(loaded.parameter_table, tables.parameter_table)
    pd.testing.assert_frame_equal(loaded.evaluation_table, tables.evaluation_table)
    assert loaded.operator_outputs == tables.operator_outputs
    assert loaded.parameter_manifest == tables.parameter_manifest
