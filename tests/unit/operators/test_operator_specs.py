import pandas as pd
import pytest

from image_gallery.cleaning.preview_policy import PreviewPolicy
from image_gallery.operators.spec import ConfiguredOperatorSpec, OperatorSpec


def _evaluate_ok(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "demo_action": config["action"],
            "demo_reason": "ok",
        }
    )


def _evaluate_missing_column(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame({"image_id": parameter_table["image_id"], "demo_action": config["action"]})


def _demo_operator_spec() -> OperatorSpec:
    return OperatorSpec(
        name="quality.demo_check",
        category="quality",
        required_parameters=["score"],
        evaluation_columns=["score", "demo_action", "demo_reason"],
        default_config={"threshold": 1.0, "action": "review"},
        action_column="demo_action",
        reason_column="demo_reason",
        evaluator=lambda frame, config: frame[["image_id", "score"]].assign(
            demo_action=config["action"],
            demo_reason="",
        ),
        preview_policy=PreviewPolicy(default_actions=["review"], caption_columns=["score"]),
    )


def test_operator_spec_evaluate_returns_declared_columns() -> None:
    spec = OperatorSpec(
        name="quality.demo_check",
        category="quality",
        required_parameters=["demo_score"],
        evaluation_columns=["demo_action", "demo_reason"],
        default_config={"action": "review"},
        action_column="demo_action",
        reason_column="demo_reason",
        evaluator=_evaluate_ok,
    )

    result = spec.evaluate(pd.DataFrame({"image_id": ["img-1"], "demo_score": [1.0]}), {"action": "drop"})

    assert result.to_dict(orient="records") == [
        {"image_id": "img-1", "demo_action": "drop", "demo_reason": "ok"}
    ]


def test_operator_spec_rejects_missing_declared_output_columns() -> None:
    spec = OperatorSpec(
        name="quality.demo_check",
        category="quality",
        required_parameters=["demo_score"],
        evaluation_columns=["demo_action", "demo_reason"],
        default_config={"action": "review"},
        action_column="demo_action",
        reason_column="demo_reason",
        evaluator=_evaluate_missing_column,
    )

    with pytest.raises(ValueError, match="missing evaluation columns"):
        spec.evaluate(pd.DataFrame({"image_id": ["img-1"], "demo_score": [1.0]}), {"action": "drop"})


def test_operator_spec_rejects_missing_required_parameters() -> None:
    spec = OperatorSpec(
        name="quality.demo_check",
        category="quality",
        required_parameters=["demo_score"],
        evaluation_columns=["demo_action", "demo_reason"],
        default_config={"action": "review"},
        action_column="demo_action",
        reason_column="demo_reason",
        evaluator=_evaluate_ok,
    )

    with pytest.raises(ValueError, match="missing required parameters"):
        spec.evaluate(pd.DataFrame({"image_id": ["img-1"]}), {"action": "drop"})


def test_configured_operator_spec_hash_excludes_policy() -> None:
    configured = ConfiguredOperatorSpec.from_spec(
        _demo_operator_spec(),
        config={"threshold": 2.0, "action": "drop"},
        source="python",
    )

    assert configured.operator_name == "quality.demo_check"
    assert configured.config["threshold"] == 2.0
    assert len(configured.operator_config_hash) == 64
