import pandas as pd

from image_gallery.operators.computers.base import ParameterRequest
from image_gallery.operators.computers.duplicate import DuplicateGroupComputer, PerceptualDuplicateGroupComputer


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


def test_perceptual_duplicate_group_computer_groups_hashes_within_distance(tmp_path) -> None:
    frame = pd.DataFrame(
        {
            "image_id": ["keeper", "near", "far"],
            "phash": ["0000000000000000", "0000000000000001", "ffffffffffffffff"],
        }
    )

    result = PerceptualDuplicateGroupComputer().compute(
        ParameterRequest(
            parameter_table=frame,
            requested_parameters=frozenset(
                {
                    "perceptual_duplicate_group_id",
                    "perceptual_duplicate_count",
                    "perceptual_duplicate_distance",
                }
            ),
            config={"max_distance": 4},
            config_hash="default",
            artifacts_dir=tmp_path,
        )
    )

    rows = result.parameter_updates.to_dict(orient="records")
    assert rows[:2] == [
        {
            "image_id": "keeper",
            "perceptual_duplicate_group_id": "perceptual-0000000000000000",
            "perceptual_duplicate_count": 2,
            "perceptual_duplicate_distance": 0,
        },
        {
            "image_id": "near",
            "perceptual_duplicate_group_id": "perceptual-0000000000000000",
            "perceptual_duplicate_count": 2,
            "perceptual_duplicate_distance": 1,
        },
    ]
    assert rows[2]["image_id"] == "far"
    assert rows[2]["perceptual_duplicate_group_id"] == ""
    assert rows[2]["perceptual_duplicate_count"] == 1
    assert pd.isna(rows[2]["perceptual_duplicate_distance"])
    pairs = result.relation_updates["perceptual_duplicate_pairs"]
    assert pairs[["relation_type", "source_image_id", "target_image_id", "score", "group_id"]].to_dict(
        orient="records"
    ) == [
        {
            "relation_type": "perceptual_duplicate",
            "source_image_id": "keeper",
            "target_image_id": "near",
            "score": 1.0 - 1.0 / 64.0,
            "group_id": "perceptual-0000000000000000",
        }
    ]


def test_perceptual_duplicate_group_computer_ignores_empty_hashes(tmp_path) -> None:
    frame = pd.DataFrame({"image_id": ["bad"], "phash": [""]})

    result = PerceptualDuplicateGroupComputer().compute(
        ParameterRequest(
            parameter_table=frame,
            requested_parameters=frozenset({"perceptual_duplicate_group_id"}),
            config={},
            config_hash="default",
            artifacts_dir=tmp_path,
        )
    )

    rows = result.parameter_updates.to_dict(orient="records")
    assert rows[0]["image_id"] == "bad"
    assert rows[0]["perceptual_duplicate_group_id"] == ""
    assert rows[0]["perceptual_duplicate_count"] == 1
    assert pd.isna(rows[0]["perceptual_duplicate_distance"])
