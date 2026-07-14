import pandas as pd
import pytest

from image_gallery.cleaning.config import parse_operator_configs
from image_gallery.cleaning.errors import UnknownOperatorError
from image_gallery.cleaning.planner import CleaningRunPlanner
from image_gallery.operators.builtin import create_default_registry
from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer, ParameterRequest, ParameterResult
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


class FeatureComputer(ParameterComputer):
    name = "feature_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"feature_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(pd.DataFrame(), {}, {}, {})


class AggregateComputer(ParameterComputer):
    name = "aggregate_computer"
    execution_mode = ExecutionMode.DATASET_AGGREGATE
    produced_parameters = frozenset({"group_id", "group_count"})
    required_parameters = frozenset({"feature_score"})
    config_parameters = frozenset({"max_distance"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(pd.DataFrame(), {}, {}, {})


class OtherComputer(ParameterComputer):
    name = "other_computer"
    execution_mode = ExecutionMode.TABLE
    produced_parameters = frozenset({"other_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(pd.DataFrame(), {}, {}, {})


def _evaluate(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame({"image_id": parameter_table["image_id"], "demo_action": "keep", "demo_reason": ""})


def _registry() -> OperatorRegistry:
    registry = OperatorRegistry()
    registry.register_parameter_computer(FeatureComputer())
    registry.register_parameter_computer(AggregateComputer())
    registry.register_parameter_computer(OtherComputer())
    registry.register_operator(
        OperatorSpec(
            name="duplicate.demo_check",
            category="duplicate",
            required_parameters=["group_id", "group_count"],
            evaluation_columns=["demo_action", "demo_reason"],
            default_config={"action": "drop"},
            action_column="demo_action",
            reason_column="demo_reason",
            evaluator=_evaluate,
        )
    )
    registry.register_operator(
        OperatorSpec(
            name="quality.other_check",
            category="quality",
            required_parameters=["other_score"],
            evaluation_columns=["demo_action", "demo_reason"],
            default_config={},
            action_column="demo_action",
            reason_column="demo_reason",
            evaluator=_evaluate,
        )
    )
    return registry


def _evaluate_other(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame({"image_id": parameter_table["image_id"], "other_action": "keep", "other_reason": ""})


def test_planner_expands_parameter_dependencies_in_topological_order() -> None:
    parsed = parse_operator_configs([{"duplicate.demo_check": {}}])

    plan = CleaningRunPlanner(_registry()).compile(parsed)

    assert [step.computer_name for step in plan.parameter_plan.steps] == [
        "feature_computer",
        "aggregate_computer",
    ]
    assert plan.parameter_plan.steps[0].requested_parameters == frozenset({"feature_score"})
    assert plan.parameter_plan.steps[1].requested_parameters == frozenset({"group_count", "group_id"})
    assert plan.parameter_plan.steps[1].upstream_computer_names == ("feature_computer",)
    assert [run.spec.name for run in plan.resolved_operator_runs] == ["duplicate.demo_check"]


def test_planner_merges_requested_parameters_per_computer() -> None:
    parsed = parse_operator_configs([{"duplicate.demo_check": {}}, {"quality.other_check": {}}])

    plan = CleaningRunPlanner(_registry()).compile(parsed)

    rows_by_name = {row["computer_name"]: row for row in plan.parameter_plan.to_frame().to_dict(orient="records")}
    names = [step.computer_name for step in plan.parameter_plan.steps]
    assert set(names) == {"feature_computer", "aggregate_computer", "other_computer"}
    assert names.index("feature_computer") < names.index("aggregate_computer")
    assert rows_by_name["aggregate_computer"]["requested_parameters"] == "group_count,group_id"
    assert rows_by_name["other_computer"]["requested_parameters"] == "other_score"


def test_planner_rejects_conflicting_parameter_computer_configs() -> None:
    registry = _registry()
    registry.register_operator(
        OperatorSpec(
            name="duplicate.other_demo_check",
            category="duplicate",
            required_parameters=["group_id"],
            evaluation_columns=["other_action", "other_reason"],
            default_config={"max_distance": 2},
            action_column="other_action",
            reason_column="other_reason",
            evaluator=_evaluate_other,
        )
    )
    parsed = parse_operator_configs(
        [
            {"duplicate.demo_check": {"max_distance": 1}},
            {"duplicate.other_demo_check": {"max_distance": 2}},
        ]
    )

    with pytest.raises(ValueError, match="conflicting parameter computer config: aggregate_computer"):
        CleaningRunPlanner(registry).compile(parsed)


def test_planner_rejects_missing_parameter_producer() -> None:
    registry = OperatorRegistry()
    registry.register_operator(
        OperatorSpec(
            name="quality.missing_check",
            category="quality",
            required_parameters=["missing_score"],
            evaluation_columns=["demo_action", "demo_reason"],
            default_config={},
            action_column="demo_action",
            reason_column="demo_reason",
            evaluator=_evaluate,
        )
    )
    parsed = parse_operator_configs([{"quality.missing_check": {}}])

    with pytest.raises(UnknownOperatorError, match="missing parameter producer"):
        CleaningRunPlanner(registry).compile(parsed)


def test_planner_rejects_dependency_cycle() -> None:
    class AComputer(ParameterComputer):
        name = "a_computer"
        execution_mode = ExecutionMode.TABLE
        produced_parameters = frozenset({"a"})
        required_parameters = frozenset({"b"})

        def compute(self, request: ParameterRequest) -> ParameterResult:
            return ParameterResult(pd.DataFrame(), {}, {}, {})

    class BComputer(ParameterComputer):
        name = "b_computer"
        execution_mode = ExecutionMode.TABLE
        produced_parameters = frozenset({"b"})
        required_parameters = frozenset({"a"})

        def compute(self, request: ParameterRequest) -> ParameterResult:
            return ParameterResult(pd.DataFrame(), {}, {}, {})

    registry = OperatorRegistry()
    registry.register_parameter_computer(AComputer())
    registry.register_parameter_computer(BComputer())
    registry.register_operator(
        OperatorSpec(
            name="quality.cycle_check",
            category="quality",
            required_parameters=["a"],
            evaluation_columns=["demo_action", "demo_reason"],
            default_config={},
            action_column="demo_action",
            reason_column="demo_reason",
            evaluator=_evaluate,
        )
    )

    with pytest.raises(ValueError, match="parameter dependency cycle"):
        CleaningRunPlanner(registry).compile(parse_operator_configs([{"quality.cycle_check": {}}]))


def test_builtin_planner_expands_perceptual_duplicate_dependencies() -> None:
    parsed = parse_operator_configs([{"perceptual_duplicate": {}}])

    plan = CleaningRunPlanner(create_default_registry()).compile(parsed)

    assert [step.computer_name for step in plan.parameter_plan.steps] == [
        "image_perceptual_hash_computer",
        "perceptual_duplicate_group_computer",
    ]
    assert plan.parameter_plan.steps[0].requested_parameters == frozenset({"phash"})
    assert plan.parameter_plan.steps[1].requested_parameters == frozenset(
        {
            "perceptual_duplicate_group_id",
            "perceptual_duplicate_count",
            "perceptual_duplicate_distance",
        }
    )


def test_builtin_planner_expands_semantic_duplicate_dependencies() -> None:
    parsed = parse_operator_configs([{"semantic_duplicate": {"provider": "fake"}}])

    plan = CleaningRunPlanner(create_default_registry()).compile(parsed)

    assert [step.computer_name for step in plan.parameter_plan.steps] == [
        "semantic_embedding_computer",
        "semantic_duplicate_group_computer",
    ]
    assert plan.parameter_plan.steps[0].requested_parameters == frozenset({"semantic_embedding_ref"})
    assert plan.parameter_plan.steps[1].requested_parameters == frozenset(
        {
            "semantic_duplicate_group_id",
            "semantic_duplicate_count",
            "semantic_duplicate_score",
            "semantic_duplicate_nearest_image_id",
        }
    )


def test_builtin_planner_passes_operator_config_to_parameter_computer() -> None:
    parsed = parse_operator_configs([{"perceptual_duplicate": {"max_distance": 0}}])

    plan = CleaningRunPlanner(create_default_registry()).compile(parsed)

    perceptual_step = plan.parameter_plan.steps[1]
    assert perceptual_step.computer_name == "perceptual_duplicate_group_computer"
    assert perceptual_step.config == {"max_distance": 0}
    assert perceptual_step.config_hash != "default"
