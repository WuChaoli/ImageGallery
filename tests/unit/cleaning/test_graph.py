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
    operators = select_operators([{"exact_duplicate": {}}], registry)

    graph = CleaningStateGraph.compile(operators, registry)

    node_ids = [node.node_id for node in graph.nodes]
    assert node_ids.index("parameter.image_hash_computer") < node_ids.index("parameter.duplicate_group_computer")
    assert node_ids.index("parameter.duplicate_group_computer") < node_ids.index("evaluation.exact_duplicate")
    assert node_ids[-1] == "merge.final_action"


def test_state_graph_preserves_complete_node_order_and_plan_hash() -> None:
    registry = create_default_registry()
    operators = select_operators([{"exact_duplicate": {}}], registry)

    graph = CleaningStateGraph.compile(operators, registry)

    assert [
        (
            node.node_id,
            node.config_hash,
            node.upstream_node_ids,
            node.checkpoint_strategy,
        )
        for node in graph.nodes
    ] == [
        ("parameter.image_hash_computer", "default", (), "batch"),
        (
            "parameter.duplicate_group_computer",
            "default",
            ("parameter.image_hash_computer",),
            "whole_node",
        ),
        (
            "evaluation.exact_duplicate",
            "c01de66f7dd8ead1d8dc0b56c4d6c5796feacd1d7f1d5326a414fd76e282318a",
            ("parameter.duplicate_group_computer",),
            "none",
        ),
        ("merge.final_action", "default", ("evaluation.exact_duplicate",), "none"),
    ]
    assert graph.plan_hash == "15d3d8c7e5f835b00a9b5950b5bd3fda602e2ba86b5e1ae302271dcaa65b9f34"


def test_state_graph_includes_evaluation_and_merge_nodes() -> None:
    registry = create_default_registry()
    operators = select_operators([{"blur": {}}], registry)

    graph = CleaningStateGraph.compile(operators, registry)

    assert "evaluation.blur" in [node.node_id for node in graph.nodes]
    assert "merge.final_action" in [node.node_id for node in graph.nodes]


def test_state_graph_rejects_conflicting_shared_node_policy() -> None:
    registry = create_default_registry()
    operators = select_operators(["blur", "contrast"], registry)

    with pytest.raises(ValueError, match="conflicting operator policy"):
        CleaningStateGraph.compile(
            operators,
            registry,
            operator_policies={
                "blur": NodePolicy(batch=BatchPolicy(size=64)),
                "contrast": NodePolicy(batch=BatchPolicy(size=256)),
            },
        )


def test_state_graph_applies_node_checkpoint_strategy_override_for_aggregate_node() -> None:
    registry = create_default_registry()
    operators = select_operators([{"exact_duplicate": {}}], registry)

    graph = CleaningStateGraph.compile(
        operators,
        registry,
        node_policy=NodePolicy(checkpoint=CheckpointPolicy(strategy="whole_node")),
    )

    node = next(node for node in graph.nodes if node.node_id == "parameter.duplicate_group_computer")
    assert node.checkpoint_strategy == "whole_node"


def test_state_graph_rejects_unsupported_parameter_checkpoint_strategy() -> None:
    registry = create_default_registry()
    operators = select_operators([{"exact_duplicate": {}}], registry)

    with pytest.raises(ValueError, match="checkpoint strategy"):
        CleaningStateGraph.compile(
            operators,
            registry,
            node_policy=NodePolicy(checkpoint=CheckpointPolicy(strategy="stage")),
        )


def test_state_graph_parameter_node_policy_hash_depends_on_runtime_policy() -> None:
    default_graph = _compile_graph_with_runtime_policy(128)
    custom_graph = _compile_graph_with_runtime_policy(64)
    default_node = next(node for node in default_graph.nodes if node.node_id == "parameter.runtime_policy_computer")
    custom_node = next(node for node in custom_graph.nodes if node.node_id == "parameter.runtime_policy_computer")

    assert default_node.policy_hash != custom_node.policy_hash


def test_semantic_graph_declares_stage_dependencies_and_artifacts() -> None:
    """semantic duplicate 应声明可持久化的 stage 级 artifact/relation contract。"""
    registry = create_default_registry()
    operators = select_operators([{"semantic_duplicate": {}}], registry)

    graph = CleaningStateGraph.compile(operators, registry)
    semantic_nodes = [node for node in graph.nodes if node.computer_name == "semantic_duplicate_group_computer"]

    assert [node.node_id for node in semantic_nodes] == [
        "parameter.semantic_duplicate_group_computer.read_embeddings",
        "parameter.semantic_duplicate_group_computer.build_index",
        "parameter.semantic_duplicate_group_computer.find_pairs",
        "parameter.semantic_duplicate_group_computer.write_relations",
    ]
    assert semantic_nodes[1].produced_artifacts == frozenset({"semantic_index"})
    assert semantic_nodes[-1].produced_relations == frozenset({"semantic_duplicate_pairs"})
    assert "evaluation.semantic_duplicate" in [
        node.node_id
        for node in graph.nodes
        if "parameter.semantic_duplicate_group_computer.write_relations" in node.upstream_node_ids
    ]
