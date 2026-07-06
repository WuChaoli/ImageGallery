import pandas as pd

from image_gallery.operators.computers.base import ParameterRequest
from image_gallery.operators.computers.derived import TableDerivedComputer


def test_table_derived_computer_produces_aspect_ratio_and_megapixels(tmp_path) -> None:
    computer = TableDerivedComputer()
    result = computer.compute(
        ParameterRequest(
            parameter_table=pd.DataFrame(
                {
                    "image_id": ["wide", "bad"],
                    "width": [400, pd.NA],
                    "height": [200, 0],
                }
            ),
            requested_parameters=frozenset({"aspect_ratio", "megapixels"}),
            config={},
            config_hash="default",
            artifacts_dir=tmp_path,
        )
    )

    rows = result.parameter_updates.to_dict(orient="records")
    assert rows[0] == {"image_id": "wide", "aspect_ratio": 2.0, "megapixels": 0.08}
    assert pd.isna(rows[1]["aspect_ratio"])
    assert pd.isna(rows[1]["megapixels"])
    assert result.parameter_manifest == {
        "aspect_ratio": {"computer": "table_derived_computer", "stage": "table_derived", "config_hash": "default"},
        "megapixels": {"computer": "table_derived_computer", "stage": "table_derived", "config_hash": "default"},
    }
