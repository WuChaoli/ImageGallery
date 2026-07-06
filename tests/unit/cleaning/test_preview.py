import pandas as pd

from image_gallery.cleaning.preview import apply_final_action, build_preview


def test_apply_final_action_uses_priority_and_operator_outputs() -> None:
    evaluation_table = pd.DataFrame(
        {
            "image_id": ["img-1", "img-2", "img-3", "img-4"],
            "image_uri": ["a", "b", "c", "d"],
            "demo_action": ["drop", "review", "keep", ""],
            "demo_reason": ["demo failed", "borderline", "", ""],
            "policy_action": ["keep", "restricted", "keep", ""],
            "policy_reason": ["", "policy hit", "", ""],
        }
    )
    operator_outputs = {
        "quality.demo_check": ["demo_action", "demo_reason"],
        "content.policy_check": ["policy_action", "policy_reason"],
    }

    result = apply_final_action(evaluation_table, operator_outputs)

    assert result["final_action"].tolist() == ["drop", "restricted", "keep", "keep"]
    assert result["final_reason"].tolist() == ["demo failed", "policy hit; borderline", "", ""]
    assert result["triggered_operator_names"].tolist() == [
        "quality.demo_check",
        "content.policy_check;quality.demo_check",
        "",
        "",
    ]


def test_build_preview_summarizes_counts_and_samples() -> None:
    evaluation_table = pd.DataFrame(
        {
            "image_id": ["img-1", "img-2", "img-3"],
            "image_uri": ["a", "b", "c"],
            "demo_action": ["drop", "review", "keep"],
            "demo_reason": ["demo failed", "borderline", ""],
        }
    )
    operator_outputs = {"quality.demo_check": ["demo_action", "demo_reason"]}

    preview = build_preview(evaluation_table, operator_outputs, limit=2)

    assert preview.total_count == 3
    assert preview.clean_count == 1
    assert preview.review_count == 1
    assert preview.dropped_count == 1
    assert preview.restricted_count == 0
    assert len(preview.sample_rows) == 2
    assert preview.operator_summary.to_dict(orient="records") == [
        {"operator_name": "quality.demo_check", "keep": 1, "review": 1, "drop": 1, "restricted": 0}
    ]
