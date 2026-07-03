import pandas as pd
import pytest

from image_gallery.cleaning.errors import UnknownOperatorError
from image_gallery.operators.backends.base import BackendAdapter, BackendOperatorRequest, BackendResult
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


class DemoBackend(BackendAdapter):
    name = "demo_backend"

    def compute_parameters(
        self,
        dataset: object,
        parameter_table: pd.DataFrame,
        requests: list[BackendOperatorRequest],
        artifacts_dir: str,
    ) -> BackendResult:
        return BackendResult(
            parameter_updates=pd.DataFrame({"image_id": parameter_table["image_id"], "demo_score": [1.0]}),
            relation_updates={},
            artifact_refs={},
        )


def _evaluate(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "demo_action": config["action"],
            "demo_reason": "ok",
        }
    )


def test_registry_resolves_operator_and_backend() -> None:
    registry = OperatorRegistry()
    backend = DemoBackend()
    spec = OperatorSpec(
        name="quality.demo_check",
        category="quality",
        backend_name=backend.name,
        parameter_columns=["demo_score"],
        evaluation_columns=["demo_action", "demo_reason"],
        default_config={"action": "review"},
        action_column="demo_action",
        reason_column="demo_reason",
        evaluator=_evaluate,
    )

    registry.register_backend(backend)
    registry.register_operator(spec)

    assert registry.get_operator("quality.demo_check") is spec
    assert registry.get_backend("demo_backend") is backend
    assert registry.resolve("quality.demo_check") == (spec, backend)
    assert registry.list_operators() == ["quality.demo_check"]


def test_registry_rejects_unknown_operator() -> None:
    registry = OperatorRegistry()

    with pytest.raises(UnknownOperatorError):
        registry.get_operator("missing.operator")


def test_registry_rejects_operator_with_missing_backend() -> None:
    registry = OperatorRegistry()
    spec = OperatorSpec(
        name="quality.demo_check",
        category="quality",
        backend_name="missing_backend",
        parameter_columns=["demo_score"],
        evaluation_columns=["demo_action", "demo_reason"],
        default_config={"action": "review"},
        action_column="demo_action",
        reason_column="demo_reason",
        evaluator=_evaluate,
    )
    registry.register_operator(spec)

    with pytest.raises(UnknownOperatorError):
        registry.resolve("quality.demo_check")
