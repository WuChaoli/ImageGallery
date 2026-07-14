from dataclasses import dataclass

import pandas as pd

from image_gallery.cleaning.config import ParsedOperatorConfig, hash_config, merge_default_config
from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


@dataclass(frozen=True)
class ResolvedOperatorRun:
    """一次运行中已绑定 spec 和配置的逻辑算子。"""

    parsed_config: ParsedOperatorConfig
    spec: OperatorSpec
    merged_config: dict[str, object]


@dataclass(frozen=True)
class ParameterExecutionStep:
    """一个已拓扑排序的参数计算步骤。"""

    computer_name: str
    requested_parameters: frozenset[str]
    required_parameters: frozenset[str]
    produced_parameters: frozenset[str]
    execution_mode: ExecutionMode
    upstream_computer_names: tuple[str, ...]
    config: dict[str, object]
    config_hash: str


@dataclass(frozen=True)
class ParameterExecutionPlan:
    """参数计算执行计划。"""

    steps: tuple[ParameterExecutionStep, ...]

    def to_frame(self) -> pd.DataFrame:
        """把执行计划转为 Notebook 友好的 DataFrame。"""
        rows = []
        for index, step in enumerate(self.steps):
            rows.append(
                {
                    "step_index": index,
                    "computer_name": step.computer_name,
                    "execution_mode": step.execution_mode.value,
                    "requested_parameters": ",".join(sorted(step.requested_parameters)),
                    "required_parameters": ",".join(sorted(step.required_parameters)),
                    "produced_parameters": ",".join(sorted(step.produced_parameters)),
                    "upstream_computers": ",".join(step.upstream_computer_names),
                    "config_hash": step.config_hash,
                }
            )
        return pd.DataFrame(
            rows,
            columns=[
                "step_index",
                "computer_name",
                "execution_mode",
                "requested_parameters",
                "required_parameters",
                "produced_parameters",
                "upstream_computers",
                "config_hash",
            ],
        )


@dataclass(frozen=True)
class CompiledCleaningPlan:
    """编译后的 Cleaner 执行计划。"""

    resolved_operator_runs: tuple[ResolvedOperatorRun, ...]
    parameter_plan: ParameterExecutionPlan
    operator_config_hashes: dict[str, str]


class CleaningRunPlanner:
    """把逻辑算子配置编译为参数计算计划。"""

    def __init__(self, registry: OperatorRegistry) -> None:
        self._registry = registry

    def compile(self, parsed_configs: list[ParsedOperatorConfig]) -> CompiledCleaningPlan:
        """编译清洗计划，不读取 dataset，不产生运行产物。"""
        resolved_runs = tuple(self._resolve_operator_configs(parsed_configs))
        target_parameters = {parameter for run in resolved_runs for parameter in run.spec.required_parameters}
        parameter_plan = self._build_parameter_plan(resolved_runs, target_parameters)
        return CompiledCleaningPlan(
            resolved_operator_runs=resolved_runs,
            parameter_plan=parameter_plan,
            operator_config_hashes={run.spec.name: run.parsed_config.config_hash for run in resolved_runs},
        )

    def _resolve_operator_configs(self, parsed_configs: list[ParsedOperatorConfig]) -> list[ResolvedOperatorRun]:
        """把用户配置绑定到逻辑算子 spec，并合并默认配置。"""
        resolved: list[ResolvedOperatorRun] = []
        for parsed_config in parsed_configs:
            spec = self._registry.get_operator(parsed_config.operator_name)
            merged = merge_default_config(parsed_config, spec.default_config)
            resolved.append(ResolvedOperatorRun(parsed_config=merged, spec=spec, merged_config=merged.config))
        return resolved

    def _build_parameter_plan(
        self,
        resolved_runs: tuple[ResolvedOperatorRun, ...],
        target_parameters: set[str],
    ) -> ParameterExecutionPlan:
        """根据目标参数反向追踪生产者，构造参数计算执行计划。"""
        requested_by_computer: dict[str, set[str]] = {}
        upstream_by_computer: dict[str, set[str]] = {}
        config_by_computer = self._parameter_computer_configs(resolved_runs)
        computer_by_name = {computer.name: computer for computer in self._registry.list_parameter_computers()}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit_parameter(parameter_name: str) -> str:
            """记录目标参数的生产 computer，并递归解析该 computer 的依赖。"""
            computer = self._registry.get_parameter_producer(parameter_name)
            requested_by_computer.setdefault(computer.name, set()).add(parameter_name)
            visit_computer(computer.name)
            return computer.name

        def visit_computer(computer_name: str) -> None:
            """深度优先遍历 computer 依赖，并在递归栈中检测循环依赖。"""
            if computer_name in visiting:
                cycle = " -> ".join([*sorted(visiting), computer_name])
                raise ValueError(f"parameter dependency cycle: {cycle}")
            if computer_name in visited:
                return
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

        # 从逻辑算子所需参数出发，反向收集所有必要的 ParameterComputer。
        for parameter_name in sorted(target_parameters):
            visit_parameter(parameter_name)

        ordered_names = self._topological_order(upstream_by_computer, computer_by_name)
        steps = []
        for computer_name in ordered_names:
            computer = computer_by_name[computer_name]
            steps.append(
                ParameterExecutionStep(
                    computer_name=computer.name,
                    requested_parameters=frozenset(requested_by_computer.get(computer.name, set())),
                    required_parameters=frozenset(computer.required_parameters),
                    produced_parameters=frozenset(computer.produced_parameters),
                    execution_mode=computer.execution_mode,
                    upstream_computer_names=tuple(sorted(upstream_by_computer.get(computer.name, set()))),
                    config=dict(config_by_computer.get(computer.name, ({}, "default"))[0]),
                    config_hash=config_by_computer.get(computer.name, ({}, "default"))[1],
                )
            )
        return ParameterExecutionPlan(steps=tuple(steps))

    def _parameter_computer_configs(
        self,
        resolved_runs: tuple[ResolvedOperatorRun, ...],
    ) -> dict[str, tuple[dict[str, object], str]]:
        """把逻辑算子配置绑定到其参数依赖闭包内的 computer。"""
        configs: dict[str, tuple[dict[str, object], str]] = {}

        def collect_computer_names(parameter_name: str, seen: set[str]) -> set[str]:
            computer = self._registry.get_parameter_producer(parameter_name)
            if computer.name in seen:
                return set()
            seen.add(computer.name)
            names = {computer.name}
            for required_parameter in computer.required_parameters:
                names.update(collect_computer_names(required_parameter, seen))
            return names

        for run in resolved_runs:
            computer_names: set[str] = set()
            for required_parameter in run.spec.required_parameters:
                computer_names.update(collect_computer_names(required_parameter, set()))

            for computer_name in sorted(computer_names):
                computer = self._registry.get_parameter_computer(computer_name)
                projected_config = {
                    key: run.merged_config[key]
                    for key in sorted(computer.config_parameters)
                    if key in run.merged_config
                }
                config_hash = hash_config(projected_config) if projected_config else "default"
                next_config = (projected_config, config_hash)
                existing_config = configs.get(computer.name)
                if existing_config is not None and existing_config != next_config:
                    raise ValueError(f"conflicting parameter computer config: {computer.name}")
                configs[computer.name] = next_config
        return configs

    def _topological_order(
        self,
        upstream_by_computer: dict[str, set[str]],
        computer_by_name: dict[str, ParameterComputer],
    ) -> list[str]:
        """按依赖关系和执行模式稳定排序参数计算步骤。"""
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
