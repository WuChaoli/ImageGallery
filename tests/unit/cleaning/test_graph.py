import pandas as pd
import pytest

from image_gallery.cleaning.graph import CleaningStateGraph
from image_gallery.cleaning.policy import BatchPolicy, CheckpointPolicy, NodePolicy
from image_gallery.cleaning.selection import select_operators
from image_gallery.operators.builtin import create_default_registry
from image_gallery.operators.computers.base import (
    ComputerRuntimePolicy,
    ExecutionMode,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


def _custom_runtime_policy_evaluator(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """用于构建自定义参数计算单元的 evaluator。"""
    size = len(parameter_table)
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "runtime_policy_action": ["keep"] * size,
            "runtime_policy_reason": [""] * size,
        }
    )


def _compile_graph_with_runtime_policy(batch_size: int) -> CleaningStateGraph:
    """编译一个仅含自定义参数节点的图用于测试运行时策略影响。"""

    class RuntimeBatchComputer(ParameterComputer):
        name = "runtime_policy_computer"
        execution_mode = ExecutionMode.PER_IMAGE
        produced_parameters = frozenset({"runtime_policy_value"})
        runtime_policy = ComputerRuntimePolicy(batch=BatchPolicy(size=batch_size))

        def compute(self, request: ParameterRequest) -> ParameterResult:
            return ParameterResult(
                parameter_updates=pd.DataFrame(
                    {
                        "image_id": request.parameter_table["image_id"],
                        "runtime_policy_value": [0] * len(request.parameter_table),
                    }
                ),
                relation_updates={},
                artifact_refs={},
                parameter_manifest={
                    "runtime_policy_value": {
                        "computer": self.name,
                        "execution_mode": self.execution_mode.value,
                        "config_hash": request.config_hash,
                    }
                },
            )

    registry = OperatorRegistry()
    registry.register_parameter_computer(RuntimeBatchComputer())
    registry.register_operator(
        OperatorSpec(
            name="test.runtime_policy_check",
            category="test",
            required_parameters=["runtime_policy_value"],
            evaluation_columns=["runtime_policy_action", "runtime_policy_reason"],
            default_config={},
            action_column="runtime_policy_action",
            reason_column="runtime_policy_reason",
            evaluator=_custom_runtime_policy_evaluator,
        )
    )
    operators = select_operators(["test.runtime_policy_check"], registry)
    return CleaningStateGraph.compile(operators, registry)


def test_state_graph_orders_by_parameter_dependencies() -> None:
    registry = create_default_registry()
    operators = select_operators([{"duplicate.exact_duplicate_check": {}}], registry)

    graph = CleaningStateGraph.compile(operators, registry)

    node_ids = [node.node_id for node in graph.nodes]
    assert node_ids.index("parameter.image_hash_computer") < node_ids.index("parameter.duplicate_group_computer")
    assert node_ids.index("parameter.duplicate_group_computer") < node_ids.index(
        "evaluation.duplicate.exact_duplicate_check"
    )
    assert node_ids[-1] == "merge.final_action"


def test_state_graph_includes_evaluation_and_merge_nodes() -> None:
    registry = create_default_registry()
    operators = select_operators([{"quality.blur_check": {}}], registry)

    graph = CleaningStateGraph.compile(operators, registry)

    assert "evaluation.quality.blur_check" in [node.node_id for node in graph.nodes]
    assert "merge.final_action" in [node.node_id for node in graph.nodes]


def test_state_graph_rejects_conflicting_shared_node_policy() -> None:
    registry = create_default_registry()
    operators = select_operators(["quality.blur_check", "quality.contrast_check"], registry)

    with pytest.raises(ValueError, match="conflicting operator policy"):
        CleaningStateGraph.compile(
            operators,
            registry,
            operator_policies={
                "quality.blur_check": NodePolicy(batch=BatchPolicy(size=64)),
                "quality.contrast_check": NodePolicy(batch=BatchPolicy(size=256)),
            },
        )


def test_state_graph_applies_node_checkpoint_strategy_override_for_aggregate_node() -> None:
    registry = create_default_registry()
    operators = select_operators([{"duplicate.exact_duplicate_check": {}}], registry)

    graph = CleaningStateGraph.compile(
        operators,
        registry,
        node_policy=NodePolicy(checkpoint=CheckpointPolicy(strategy="whole_node")),
    )

    node = next(node for node in graph.nodes if node.node_id == "parameter.duplicate_group_computer")
    assert node.checkpoint_strategy == "whole_node"


def test_state_graph_rejects_unsupported_parameter_checkpoint_strategy() -> None:
    registry = create_default_registry()
    operators = select_operators([{"duplicate.exact_duplicate_check": {}}], registry)

    with pytest.raises(ValueError, match="checkpoint strategy"):
        CleaningStateGraph.compile(
            operators,
            registry,
            node_policy=NodePolicy(checkpoint=CheckpointPolicy(strategy="stage")),
        )


def test_state_graph_parameter_node_policy_hash_depends_on_runtime_policy() -> None:
    default_graph = _compile_graph_with_runtime_policy(128)
    custom_graph = _compile_graph_with_runtime_policy(64)
    default_node = next(
        node for node in default_graph.nodes if node.node_id == "parameter.runtime_policy_computer"
    )
    custom_node = next(
        node for node in custom_graph.nodes if node.node_id == "parameter.runtime_policy_computer"
    )

    assert default_node.policy_hash != custom_node.policy_hash
