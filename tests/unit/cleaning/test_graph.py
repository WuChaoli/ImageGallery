import pytest

from image_gallery.cleaning.graph import CleaningStateGraph
from image_gallery.cleaning.policy import BatchPolicy, NodePolicy
from image_gallery.cleaning.selection import select_operators
from image_gallery.operators.builtin import create_default_registry


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
