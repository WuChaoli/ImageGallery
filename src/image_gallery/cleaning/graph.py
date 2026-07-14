import json
from dataclasses import asdict, dataclass, field
from hashlib import sha256

import pandas as pd

from image_gallery.cleaning.config import hash_config
from image_gallery.cleaning.policy import ComputerRuntimePolicy, NodePolicy
from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import ConfiguredOperatorSpec


@dataclass(frozen=True)
class GraphNode:
    """状态图中的节点定义。"""

    node_id: str
    node_type: str
    operator_name: str | None
    computer_name: str | None
    stage_name: str | None
    execution_mode: ExecutionMode | None
    required_parameters: frozenset[str]
    produced_parameters: frozenset[str]
    config_hash: str
    policy_hash: str
    upstream_node_ids: tuple[str, ...]
    checkpoint_strategy: str
    required_artifacts: frozenset[str] = field(default_factory=frozenset)
    produced_artifacts: frozenset[str] = field(default_factory=frozenset)
    required_relations: frozenset[str] = field(default_factory=frozenset)
    produced_relations: frozenset[str] = field(default_factory=frozenset)
    artifact_contract: str = "none"
    cache_policy: str = "run"


@dataclass(frozen=True)
class CleaningStateGraph:
    """清洗状态图编译结果。"""

    nodes: tuple[GraphNode, ...]
    plan_hash: str

    @classmethod
    def compile(
        cls,
        configured_operators: list[ConfiguredOperatorSpec],
        registry: OperatorRegistry,
        node_policy: NodePolicy | None = None,
        operator_policies: dict[str, NodePolicy] | None = None,
    ) -> "CleaningStateGraph":
        """按依赖关系编译状态图。"""
        return compile_state_graph(
            configured_operators=configured_operators,
            registry=registry,
            node_policy=node_policy,
            operator_policies=operator_policies,
        )

    def to_frame(self) -> pd.DataFrame:
        """将图节点序列化为可展示 DataFrame。"""
        return pd.DataFrame(
            [
                {
                    "node_id": node.node_id,
                    "node_type": node.node_type,
                    "operator_name": node.operator_name,
                    "computer_name": node.computer_name,
                    "stage_name": node.stage_name,
                    "execution_mode": node.execution_mode.value if node.execution_mode else None,
                    "required_parameters": sorted(node.required_parameters),
                    "produced_parameters": sorted(node.produced_parameters),
                    "upstream_node_ids": sorted(node.upstream_node_ids),
                    "config_hash": node.config_hash,
                    "policy_hash": node.policy_hash,
                    "checkpoint_strategy": node.checkpoint_strategy,
                    "required_artifacts": sorted(node.required_artifacts),
                    "produced_artifacts": sorted(node.produced_artifacts),
                    "required_relations": sorted(node.required_relations),
                    "produced_relations": sorted(node.produced_relations),
                    "artifact_contract": node.artifact_contract,
                    "cache_policy": node.cache_policy,
                }
                for node in self.nodes
            ]
        )


def _select_evaluation_node_policy(
    operator_policies: dict[str, NodePolicy] | None,
    operator_name: str,
    default_node_policy: NodePolicy,
) -> NodePolicy:
    """返回某个算子的运行策略（含默认值）。"""
    if not operator_policies:
        return default_node_policy

    override = operator_policies.get(operator_name)
    if override is None:
        return default_node_policy
    return NodePolicy.merge(default_node_policy, override)


def _select_parameter_node_policies(
    configured_operators: list[ConfiguredOperatorSpec],
    registry: OperatorRegistry,
    upstream_by_computer: dict[str, set[str]],
    node_policy: NodePolicy | None,
    operator_policies: dict[str, NodePolicy] | None,
) -> dict[str, NodePolicy]:
    """把算子策略映射到参数 computer，并检测同一 computer 的冲突。"""
    policy_by_computer: dict[str, NodePolicy] = {}

    for configured in configured_operators:
        operator_policy = operator_policies.get(configured.spec.name) if operator_policies else None

        operator_scope: set[str] = set()

        for parameter_name in configured.spec.required_parameters:
            root_computer = registry.get_parameter_producer(parameter_name)
            stack = [root_computer.name]
            while stack:
                computer_name = stack.pop()
                if computer_name in operator_scope:
                    continue
                operator_scope.add(computer_name)
                stack.extend(upstream_by_computer.get(computer_name, set()))

        for computer_name in operator_scope:
            computer = registry.get_parameter_computer(computer_name)
            runtime_node_policy = _runtime_policy_to_node_policy(computer.runtime_policy)
            merged_policy = runtime_node_policy
            if node_policy is not None:
                merged_policy = NodePolicy.merge(merged_policy, node_policy)
            if operator_policy is not None:
                merged_policy = NodePolicy.merge(merged_policy, operator_policy)
            prior = policy_by_computer.get(computer.name)
            if prior is None:
                policy_by_computer[computer.name] = merged_policy
                continue
            if prior != merged_policy:
                raise ValueError(f"conflicting operator policy for parameter computer: {computer.name}")
    return policy_by_computer


def _runtime_policy_to_node_policy(runtime_policy: ComputerRuntimePolicy) -> NodePolicy:
    """将参数计算单元运行策略映射为节点策略。"""
    return NodePolicy(
        batch=runtime_policy.batch,
        checkpoint=runtime_policy.checkpoint,
        failure=runtime_policy.failure,
        resources=runtime_policy.resources,
        artifacts=runtime_policy.artifacts,
    )


def _collect_parameter_plan(
    configured_operators: list[ConfiguredOperatorSpec],
    registry: OperatorRegistry,
) -> tuple[
    tuple[str, ...],
    dict[str, set[str]],
    dict[str, str],
]:
    """展开目标参数所需的参数计算器，返回排序与参数配置。"""
    target_parameters = {
        parameter for configured in configured_operators for parameter in configured.spec.required_parameters
    }
    if not target_parameters:
        return tuple(), {}, {}

    computer_by_name = {computer.name: computer for computer in registry.list_parameter_computers()}
    visited: set[str] = set()
    visiting: set[str] = set()
    upstream_by_computer: dict[str, set[str]] = {}
    config_by_computer: dict[str, tuple[dict[str, object], str]] = {}

    def visit_parameter(parameter_name: str) -> str:
        computer = registry.get_parameter_producer(parameter_name)
        visit_computer(computer.name)
        return computer.name

    def visit_computer(computer_name: str) -> None:
        if computer_name in visited:
            return
        if computer_name in visiting:
            cycle = " -> ".join([*sorted(visiting), computer_name])
            raise ValueError(f"parameter dependency cycle: {cycle}")

        visiting.add(computer_name)
        computer = computer_by_name[computer_name]
        upstream_names: set[str] = set()
        for required_parameter in computer.required_parameters:
            upstream_name = visit_parameter(required_parameter)
            if upstream_name != computer_name:
                upstream_names.add(upstream_name)
        upstream_by_computer[computer_name] = upstream_names
        visiting.remove(computer_name)
        visited.add(computer_name)

    for parameter_name in sorted(target_parameters):
        visit_parameter(parameter_name)

    ordered_computer_names = _topological_computers(
        {name: set(upstreams) for name, upstreams in upstream_by_computer.items()},
        computer_by_name,
    )

    def collect_computer_names(parameter_name: str, seen: set[str]) -> set[str]:
        computer = registry.get_parameter_producer(parameter_name)
        if computer.name in seen:
            return set()
        seen.add(computer.name)
        names = {computer.name}
        for required_parameter in computer.required_parameters:
            names.update(collect_computer_names(required_parameter, seen))
        return names

    for configured in configured_operators:
        computer_names: set[str] = set()
        for required_parameter in configured.spec.required_parameters:
            computer_names.update(collect_computer_names(required_parameter, set()))

        for computer_name in sorted(computer_names):
            computer = registry.get_parameter_computer(computer_name)
            projected_config = {
                key: configured.config[key] for key in sorted(computer.config_parameters) if key in configured.config
            }
            config_hash = hash_config(projected_config) if projected_config else "default"
            entry = (projected_config, config_hash)
            prior = config_by_computer.get(computer.name)
            if prior is not None and prior != entry:
                raise ValueError(f"conflicting parameter computer config: {computer.name}")
            config_by_computer[computer.name] = entry

    return (
        tuple(ordered_computer_names),
        upstream_by_computer,
        {name: values[1] for name, values in config_by_computer.items()},
    )


def _topological_computers(
    upstream_by_computer: dict[str, set[str]],
    computer_by_name: dict[str, ParameterComputer],
) -> list[str]:
    """按 execution mode 与名称进行稳定拓扑排序。"""
    mode_order = {
        ExecutionMode.PER_IMAGE: 0,
        ExecutionMode.TABLE: 1,
        ExecutionMode.DATASET_AGGREGATE: 2,
    }
    remaining = {name: set(upstreams) for name, upstreams in upstream_by_computer.items()}
    ordered: list[str] = []

    while remaining:
        ready = sorted(
            (name for name, upstreams in remaining.items() if not upstreams),
            key=lambda name: (mode_order[computer_by_name[name].execution_mode], name),
        )
        if not ready:
            cycle = " -> ".join(sorted(remaining))
            raise ValueError(f"parameter dependency cycle: {cycle}")
        for name in ready:
            ordered.append(name)
            remaining.pop(name)
        for upstreams in remaining.values():
            upstreams.difference_update(ready)

    return ordered


def _checkpoint_strategy(
    execution_mode: ExecutionMode,
    computer: ParameterComputer,
    policy: NodePolicy,
) -> str:
    """按能力与策略推断参数节点 checkpoint。"""
    if not policy.checkpoint.enabled:
        return "none"

    requested_strategy = policy.checkpoint.strategy
    if requested_strategy != "auto" and requested_strategy not in computer.capability.checkpoint_strategies:
        raise ValueError(
            f"unsupported checkpoint strategy '{requested_strategy}' for parameter computer: {computer.name}"
        )
    if requested_strategy != "auto":
        return requested_strategy

    if execution_mode == ExecutionMode.DATASET_AGGREGATE:
        if "whole_node" in computer.capability.checkpoint_strategies:
            return "whole_node"
    if "batch" in computer.capability.checkpoint_strategies:
        return "batch"
    if computer.capability.checkpoint_strategies:
        return next(iter(sorted(computer.capability.checkpoint_strategies)))
    return "none"


def _policy_hash(policy: NodePolicy) -> str:
    """计算 NodePolicy 的稳定 hash。"""
    return hash_config(asdict(policy))


def _hash_graph_nodes(nodes: tuple[GraphNode, ...]) -> str:
    """给状态图做稳定哈希。"""
    payload = {
        "nodes": [
            {
                "node_id": node.node_id,
                "node_type": node.node_type,
                "operator_name": node.operator_name,
                "computer_name": node.computer_name,
                "stage_name": node.stage_name,
                "execution_mode": node.execution_mode.value if node.execution_mode else None,
                "required_parameters": sorted(node.required_parameters),
                "produced_parameters": sorted(node.produced_parameters),
                "config_hash": node.config_hash,
                "policy_hash": node.policy_hash,
                "upstream_node_ids": list(node.upstream_node_ids),
                "checkpoint_strategy": node.checkpoint_strategy,
                "required_artifacts": sorted(node.required_artifacts),
                "produced_artifacts": sorted(node.produced_artifacts),
                "required_relations": sorted(node.required_relations),
                "produced_relations": sorted(node.produced_relations),
                "artifact_contract": node.artifact_contract,
                "cache_policy": node.cache_policy,
            }
            for node in nodes
        ]
    }
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload_json.encode("utf-8")).hexdigest()


def _parameter_terminal_node_id(computer: ParameterComputer) -> str:
    """返回某个 parameter computer 在图中的最终产物节点。"""
    if computer.stages:
        return f"parameter.{computer.name}.{computer.stages[-1].name}"
    return f"parameter.{computer.name}"


def compile_state_graph(
    configured_operators: list[ConfiguredOperatorSpec],
    registry: OperatorRegistry,
    node_policy: NodePolicy | None = None,
    operator_policies: dict[str, NodePolicy] | None = None,
) -> CleaningStateGraph:
    """按依赖关系编译清洗状态图。"""
    default_node_policy = node_policy if node_policy is not None else NodePolicy()

    operator_policies_by_operator = {
        configured.spec.name: _select_evaluation_node_policy(
            operator_policies, configured.spec.name, default_node_policy
        )
        for configured in configured_operators
    }

    ordered_computer_names, upstream_by_computer, config_hash_by_computer = _collect_parameter_plan(
        configured_operators, registry
    )
    parameter_node_policies = _select_parameter_node_policies(
        configured_operators,
        registry,
        upstream_by_computer=upstream_by_computer,
        node_policy=node_policy,
        operator_policies=operator_policies,
    )

    parameter_nodes: list[GraphNode] = []
    for computer_name in ordered_computer_names:
        computer = registry.get_parameter_computer(computer_name)
        policy = parameter_node_policies[computer_name]
        upstream_node_ids = tuple(
            sorted(
                _parameter_terminal_node_id(registry.get_parameter_computer(upstream))
                for upstream in upstream_by_computer[computer_name]
            )
        )
        if computer.stages:
            previous_upstreams = upstream_node_ids
            for index, stage in enumerate(computer.stages):
                produced_parameters = (
                    frozenset(computer.produced_parameters) if index == len(computer.stages) - 1 else frozenset()
                )
                parameter_nodes.append(
                    GraphNode(
                        node_id=f"parameter.{computer_name}.{stage.name}",
                        node_type="parameter",
                        operator_name=None,
                        computer_name=computer_name,
                        stage_name=stage.name,
                        execution_mode=computer.execution_mode,
                        required_parameters=frozenset(computer.required_parameters) if index == 0 else frozenset(),
                        produced_parameters=produced_parameters,
                        config_hash=config_hash_by_computer.get(computer_name, "default"),
                        policy_hash=_policy_hash(policy),
                        upstream_node_ids=previous_upstreams,
                        checkpoint_strategy=_checkpoint_strategy(computer.execution_mode, computer, policy),
                        required_artifacts=stage.required_artifacts,
                        produced_artifacts=stage.produced_artifacts,
                        required_relations=stage.required_relations,
                        produced_relations=stage.produced_relations,
                        artifact_contract=stage.artifact_contract,
                        cache_policy=stage.cache_policy,
                    )
                )
                previous_upstreams = (f"parameter.{computer_name}.{stage.name}",)
            continue

        parameter_nodes.append(
            GraphNode(
                node_id=f"parameter.{computer_name}",
                node_type="parameter",
                operator_name=None,
                computer_name=computer_name,
                stage_name="parameter",
                execution_mode=computer.execution_mode,
                required_parameters=frozenset(computer.required_parameters),
                produced_parameters=frozenset(computer.produced_parameters),
                config_hash=config_hash_by_computer.get(computer_name, "default"),
                policy_hash=_policy_hash(policy),
                upstream_node_ids=upstream_node_ids,
                checkpoint_strategy=_checkpoint_strategy(computer.execution_mode, computer, policy),
            )
        )

    evaluation_nodes: list[GraphNode] = []
    evaluation_node_ids: list[str] = []
    for configured in sorted(configured_operators, key=lambda item: item.spec.name):
        upstream: list[str] = []
        for parameter_name in sorted(configured.spec.required_parameters):
            computer = registry.get_parameter_producer(parameter_name)
            upstream_node_id = _parameter_terminal_node_id(computer)
            if upstream_node_id not in upstream:
                upstream.append(upstream_node_id)
        policy = operator_policies_by_operator[configured.spec.name]
        evaluation_node = GraphNode(
            node_id=f"evaluation.{configured.spec.name}",
            node_type="evaluation",
            operator_name=configured.spec.name,
            computer_name=None,
            stage_name="evaluation",
            execution_mode=None,
            required_parameters=frozenset(configured.spec.required_parameters),
            produced_parameters=frozenset(configured.spec.evaluation_columns),
            config_hash=configured.operator_config_hash,
            policy_hash=_policy_hash(policy),
            upstream_node_ids=tuple(sorted(upstream)),
            checkpoint_strategy="none",
        )
        evaluation_nodes.append(evaluation_node)
        evaluation_node_ids.append(evaluation_node.node_id)

    merge_node = GraphNode(
        node_id="merge.final_action",
        node_type="merge",
        operator_name=None,
        computer_name=None,
        stage_name="merge",
        execution_mode=None,
        required_parameters=frozenset(),
        produced_parameters=frozenset({"final_action", "final_reason", "triggered_operator_names"}),
        config_hash="default",
        policy_hash=_policy_hash(default_node_policy),
        upstream_node_ids=tuple(sorted(evaluation_node_ids)),
        checkpoint_strategy="none",
    )

    ordered_nodes = tuple(
        [
            *parameter_nodes,
            *evaluation_nodes,
            merge_node,
        ]
    )
    return CleaningStateGraph(nodes=ordered_nodes, plan_hash=_hash_graph_nodes(ordered_nodes))
