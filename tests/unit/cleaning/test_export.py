from pathlib import Path

import pandas as pd

from image_gallery.cleaning.export import export_cleaning_result
from image_gallery.cleaning.tables import CleaningTables


def _tables() -> CleaningTables:
    return CleaningTables(
        parameter_table=pd.DataFrame(
            {
                "image_id": ["img-1", "img-2", "img-3"],
                "image_uri": ["a", "b", "c"],
                "demo_score": [0.1, 0.2, 0.3],
            }
        ),
        evaluation_table=pd.DataFrame(
            {
                "image_id": ["img-1", "img-2", "img-3"],
                "image_uri": ["a", "b", "c"],
                "final_action": ["keep", "review", "drop"],
                "final_reason": ["", "check", "bad"],
            }
        ),
        operator_outputs={},
        parameter_manifest={},
    )


def test_export_cleaning_result_writes_view_dataset(tmp_path: Path) -> None:
    exported = export_cleaning_result("review", _tables(), str(tmp_path / "review.parquet"))

    assert exported.to_frame().to_dict(orient="records") == [
        {"image_id": "img-2", "image_uri": "b", "final_action": "review", "final_reason": "check"}
    ]


def test_export_cleaning_result_supports_all_stage3_kinds(tmp_path: Path) -> None:
    tables = _tables()

    assert export_cleaning_result("parameters", tables, str(tmp_path / "parameters.parquet")).count() == 3
    assert export_cleaning_result("evaluations", tables, str(tmp_path / "evaluations.parquet")).count() == 3
    assert export_cleaning_result("full", tables, str(tmp_path / "full.parquet")).count() == 3
    assert export_cleaning_result("clean", tables, str(tmp_path / "clean.parquet")).count() == 1
    assert export_cleaning_result("dropped", tables, str(tmp_path / "dropped.parquet")).count() == 1
