import importlib
from collections.abc import Iterable, Mapping

import pandas as pd
import pytest

from image_gallery.cleaning.config import hash_config, parse_operator_configs
from image_gallery.cleaning.execution import build_dry_run_result
from image_gallery.cleaning.graph import CleaningStateGraph
from image_gallery.cleaning.planner import CleaningRunPlanner
from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer, ParameterRequest, ParameterResult
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import ConfiguredOperatorSpec, OperatorSpec


class SourceComputer(ParameterComputer):
    name = "source_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"source_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(pd.DataFrame(), {}, {}, {})


class AggregateComputer(ParameterComputer):
    name = "aggregate_computer"
    execution_mode = ExecutionMode.DATASET_AGGREGATE
    produced_parameters = frozenset({"group_id"})
    required_parameters = frozenset({"source_score"})
    config_parameters = frozenset({"max_distance"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(pd.DataFrame(), {}, {}, {})


def _evaluate(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "demo_action": "keep",
            "demo_reason": "",
        }
    )


def _operator(name: str) -> OperatorSpec:
    return OperatorSpec(
        name=name,
        category="demo",
        required_parameters=["group_id"],
        evaluation_columns=["demo_action", "demo_reason"],
        default_config={},
        action_column="demo_action",
        reason_column="demo_reason",
        evaluator=_evaluate,
    )


def _registry() -> OperatorRegistry:
    registry = OperatorRegistry()
    registry.register_parameter_computer(SourceComputer())
    registry.register_parameter_computer(AggregateComputer())
    return registry


def _resolve_configs(
    operator_configs: list[tuple[OperatorSpec, dict[str, object]]],
    registry: OperatorRegistry,
) -> dict[str, tuple[dict[str, object], str]]:
    try:
        module = importlib.import_module("image_gallery.cleaning._parameter_config")
    except ModuleNotFoundError:
        pytest.fail("private ParameterComputer config resolver is missing")
    return module.resolve_parameter_computer_configs(operator_configs, registry)


def test_resolver_projects_config_across_dependency_closure() -> None:
    configs = _resolve_configs(
        [(_operator("demo.primary"), {"max_distance": 3, "ignored": True})],
        _registry(),
    )

    assert configs == {
        "aggregate_computer": ({"max_distance": 3}, hash_config({"max_distance": 3})),
        "source_computer": ({}, "default"),
    }


def test_resolver_rejects_conflicting_shared_computer_config() -> None:
    registry = _registry()

    with pytest.raises(ValueError, match="conflicting parameter computer config: aggregate_computer"):
        _resolve_configs(
            [
                (_operator("demo.first"), {"max_distance": 1}),
                (_operator("demo.second"), {"max_distance": 2}),
            ],
            registry,
        )


def test_planner_graph_and_dry_run_delegate_to_shared_resolver(monkeypatch: pytest.MonkeyPatch) -> None:
    parameter_config = importlib.import_module("image_gallery.cleaning._parameter_config")
    original_resolver = parameter_config.resolve_parameter_computer_configs
    calls: list[tuple[str, ...]] = []

    def tracking_resolver(
        operator_configs: Iterable[tuple[OperatorSpec, Mapping[str, object]]],
        registry: OperatorRegistry,
    ) -> dict[str, tuple[dict[str, object], str]]:
        items = list(operator_configs)
        calls.append(tuple(spec.name for spec, _ in items))
        return original_resolver(items, registry)

    monkeypatch.setattr(parameter_config, "resolve_parameter_computer_configs", tracking_resolver)
    registry = _registry()
    spec = _operator("demo.shared")
    registry.register_operator(spec)
    configured = ConfiguredOperatorSpec.from_spec(spec, {"max_distance": 4}, source="test")

    CleaningRunPlanner(registry).compile(parse_operator_configs([{"demo.shared": {"max_distance": 4}}]))
    graph = CleaningStateGraph.compile([configured], registry)
    build_dry_run_result(graph, [configured], registry=registry)

    assert calls == [("demo.shared",), ("demo.shared",), ("demo.shared",)]
