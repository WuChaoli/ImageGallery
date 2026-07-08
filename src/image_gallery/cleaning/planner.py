from dataclasses import dataclass

import pandas as pd

from image_gallery.cleaning.config import ParsedOperatorConfig, merge_default_config
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
        parameter_plan = self._build_parameter_plan(target_parameters)
        return CompiledCleaningPlan(
            resolved_operator_runs=resolved_runs,
            parameter_plan=parameter_plan,
            operator_config_hashes={run.spec.name: run.parsed_config.config_hash for run in resolved_runs},
        )

    def _resolve_operator_configs(self, parsed_configs: list[ParsedOperatorConfig]) -> list[ResolvedOperatorRun]:
        resolved: list[ResolvedOperatorRun] = []
        for parsed_config in parsed_configs:
            spec = self._registry.get_operator(parsed_config.operator_name)
            merged = merge_default_config(parsed_config, spec.default_config)
            resolved.append(ResolvedOperatorRun(parsed_config=merged, spec=spec, merged_config=merged.config))
        return resolved

    def _build_parameter_plan(self, target_parameters: set[str]) -> ParameterExecutionPlan:
        requested_by_computer: dict[str, set[str]] = {}
        upstream_by_computer: dict[str, set[str]] = {}
        computer_by_name = {computer.name: computer for computer in self._registry.list_parameter_computers()}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit_parameter(parameter_name: str) -> str:
            computer = self._registry.get_parameter_producer(parameter_name)
            requested_by_computer.setdefault(computer.name, set()).add(parameter_name)
            visit_computer(computer.name)
            return computer.name

        def visit_computer(computer_name: str) -> None:
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
                )
            )
        return ParameterExecutionPlan(steps=tuple(steps))

    def _topological_order(
        self,
        upstream_by_computer: dict[str, set[str]],
        computer_by_name: dict[str, ParameterComputer],
    ) -> list[str]:
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
