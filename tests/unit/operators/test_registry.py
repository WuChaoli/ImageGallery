import pandas as pd
import pytest

from image_gallery.cleaning.errors import UnknownOperatorError
from image_gallery.operators.computers.base import (
    ComputeStage,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


class DemoComputer(ParameterComputer):
    name = "demo_computer"
    stage = ComputeStage.IMAGE_BATCH
    produced_parameters = frozenset({"demo_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(
            parameter_updates=pd.DataFrame({"image_id": request.parameter_table["image_id"], "demo_score": [1.0]}),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={},
        )


def _evaluate(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "demo_action": config["action"],
            "demo_reason": "ok",
        }
    )


def test_registry_resolves_operator_and_parameter_computer() -> None:
    registry = OperatorRegistry()
    computer = DemoComputer()
    spec = OperatorSpec(
        name="quality.demo_check",
        category="quality",
        required_parameters=["demo_score"],
        evaluation_columns=["demo_action", "demo_reason"],
        default_config={"action": "review"},
        action_column="demo_action",
        reason_column="demo_reason",
        evaluator=_evaluate,
    )

    registry.register_parameter_computer(computer)
    registry.register_operator(spec)

    assert registry.get_operator("quality.demo_check") is spec
    assert registry.get_parameter_computer("demo_computer") is computer
    assert registry.find_computers_for_parameters({"demo_score"}) == [computer]
    assert registry.list_operators() == ["quality.demo_check"]


def test_registry_rejects_unknown_operator() -> None:
    registry = OperatorRegistry()

    with pytest.raises(UnknownOperatorError):
        registry.get_operator("missing.operator")


def test_registry_rejects_missing_parameter_producer() -> None:
    registry = OperatorRegistry()

    with pytest.raises(UnknownOperatorError, match="missing parameter producers"):
        registry.find_computers_for_parameters({"missing_score"})
