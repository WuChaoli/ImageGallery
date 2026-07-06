import pandas as pd

from image_gallery.operators.computers.base import ParameterRequest
from image_gallery.operators.computers.duplicate import DuplicateGroupComputer


def test_duplicate_group_computer_marks_repeated_hashes(tmp_path) -> None:
    frame = pd.DataFrame(
        {
            "image_id": ["first", "unique", "second"],
            "content_hash": ["h1", "h2", "h1"],
        }
    )

    result = DuplicateGroupComputer().compute(
        ParameterRequest(
            parameter_table=frame,
            requested_parameters=frozenset({"exact_duplicate_group_id", "exact_duplicate_count"}),
            config={},
            config_hash="default",
            artifacts_dir=tmp_path,
        )
    )

    rows = result.parameter_updates.to_dict(orient="records")
    assert rows == [
        {"image_id": "first", "exact_duplicate_group_id": "exact-h1", "exact_duplicate_count": 2},
        {"image_id": "unique", "exact_duplicate_group_id": "", "exact_duplicate_count": 1},
        {"image_id": "second", "exact_duplicate_group_id": "exact-h1", "exact_duplicate_count": 2},
    ]
    assert "duplicate_pairs" in result.relation_updates
