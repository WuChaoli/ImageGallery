import importlib
from collections.abc import Iterable, Mapping
from typing import cast

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

    def __init__(self) -> None:
        self.checked_configs: list[dict[str, object]] = []

    def before_run_check(self, config: Mapping[str, object] | None = None) -> None:
        self.checked_configs.append(dict(config or {}))

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


def _configured_operators(
    registry: OperatorRegistry,
    *entries: tuple[str, int],
) -> list[ConfiguredOperatorSpec]:
    configured_operators: list[ConfiguredOperatorSpec] = []
    for name, max_distance in entries:
        spec = _operator(name)
        registry.register_operator(spec)
        configured_operators.append(
            ConfiguredOperatorSpec.from_spec(spec, {"max_distance": max_distance}, source="test")
        )
    return configured_operators


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
    calls: list[
        tuple[
            list[tuple[str, dict[str, object]]],
            OperatorRegistry,
            dict[str, tuple[dict[str, object], str]],
        ]
    ] = []

    def tracking_resolver(
        operator_configs: Iterable[tuple[OperatorSpec, Mapping[str, object]]],
        registry: OperatorRegistry,
    ) -> dict[str, tuple[dict[str, object], str]]:
        items = list(operator_configs)
        resolved = original_resolver(items, registry)
        calls.append(
            (
                [(spec.name, dict(config)) for spec, config in items],
                registry,
                resolved,
            )
        )
        return resolved

    monkeypatch.setattr(parameter_config, "resolve_parameter_computer_configs", tracking_resolver)
    registry = _registry()
    configured = _configured_operators(registry, ("demo.shared", 4))[0]
    expected_hash = hash_config({"max_distance": 4})
    expected_resolution = {
        "aggregate_computer": ({"max_distance": 4}, expected_hash),
        "source_computer": ({}, "default"),
    }

    plan = CleaningRunPlanner(registry).compile(parse_operator_configs([{"demo.shared": {"max_distance": 4}}]))
    graph = CleaningStateGraph.compile([configured], registry)
    build_dry_run_result(graph, [configured], registry=registry)

    aggregate_step = next(step for step in plan.parameter_plan.steps if step.computer_name == "aggregate_computer")
    aggregate_node = next(node for node in graph.nodes if node.computer_name == "aggregate_computer")
    aggregate_computer = cast(AggregateComputer, registry.get_parameter_computer("aggregate_computer"))
    assert aggregate_step.config == {"max_distance": 4}
    assert aggregate_step.config_hash == expected_hash
    assert aggregate_node.config_hash == expected_hash
    assert aggregate_computer.checked_configs == [{"max_distance": 4}]
    assert len(calls) == 3
    for operator_configs, call_registry, resolved in calls:
        assert operator_configs == [("demo.shared", {"max_distance": 4})]
        assert call_registry is registry
        assert resolved == expected_resolution


def test_graph_rejects_conflicting_shared_computer_config() -> None:
    registry = _registry()
    configured_operators = _configured_operators(
        registry,
        ("demo.first", 1),
        ("demo.second", 2),
    )

    with pytest.raises(ValueError, match="conflicting parameter computer config: aggregate_computer"):
        CleaningStateGraph.compile(configured_operators, registry)


def test_dry_run_rejects_conflicting_shared_computer_config() -> None:
    registry = _registry()
    configured_operators = _configured_operators(
        registry,
        ("demo.first", 1),
        ("demo.second", 2),
    )
    graph = CleaningStateGraph.compile(configured_operators[:1], registry)

    with pytest.raises(ValueError, match="conflicting parameter computer config: aggregate_computer"):
        build_dry_run_result(graph, configured_operators, registry=registry)
