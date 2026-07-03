import pandas as pd
import pytest

from image_gallery.operators.spec import OperatorSpec


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


def test_operator_spec_evaluate_returns_declared_columns() -> None:
    spec = OperatorSpec(
        name="quality.demo_check",
        category="quality",
        backend_name="demo_backend",
        parameter_columns=["demo_score"],
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
        backend_name="demo_backend",
        parameter_columns=["demo_score"],
        evaluation_columns=["demo_action", "demo_reason"],
        default_config={"action": "review"},
        action_column="demo_action",
        reason_column="demo_reason",
        evaluator=_evaluate_missing_column,
    )

    with pytest.raises(ValueError, match="missing evaluation columns"):
        spec.evaluate(pd.DataFrame({"image_id": ["img-1"], "demo_score": [1.0]}), {"action": "drop"})
