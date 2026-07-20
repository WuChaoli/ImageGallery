"""Execution layer for cleaner lifecycle."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pandas as pd

import image_gallery.cleaning._parameter_config as _parameter_config
from image_gallery.cleaning._dataset_compat import (
    normalize_identifier_columns,
    read_dataset_fingerprint,
    read_dataset_frame,
)
from image_gallery.cleaning.config import OperatorConfigInput
from image_gallery.cleaning.events import RuntimeEvent
from image_gallery.cleaning.graph import CleaningStateGraph
from image_gallery.cleaning.policy import NodePolicy
from image_gallery.cleaning.preview_policy import PreviewPolicy
from image_gallery.cleaning.result import CleanerResult
from image_gallery.cleaning.runtime import CleaningRuntime, RunOptions
from image_gallery.cleaning.selection import OperatorSelectorInput, select_operators
from image_gallery.dataset import Dataset
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import ConfiguredOperatorSpec


def _default_cache_root() -> Path:
    """返回默认清洗运行时缓存目录。"""
    return Path.home() / ".cache" / "image_gallery" / "cleaning" / "runs"


@dataclass(frozen=True)
class DryRunResult:
    """dry-run 的最小返回壳。"""

    selected_operators: list[str]
    expanded_selectors: list[str]
    graph_nodes: list[str]
    policy_overrides: dict[str, object]
    warnings: list[str]
    errors: list[str]
    estimated_artifacts: list[str]
    preview_policies: dict[str, object]


def build_dry_run_result(
    graph: CleaningStateGraph,
    configured_operators: list[ConfiguredOperatorSpec],
    dataset: Dataset | None = None,
    registry: OperatorRegistry | None = None,
) -> DryRunResult:
    """构建不执行参数计算的运行前诊断。"""
    errors: list[str] = []
    warnings: list[str] = []
    if dataset is not None:
        frame = normalize_identifier_columns(read_dataset_frame(dataset))
        required = ["image_id"]
        if hasattr(dataset, "read_image_bytes"):
            required.append("image_uri")
        for required_column in required:
            if required_column not in frame.columns:
                errors.append(f"dataset.{required_column} column is required")
    elif dataset is None:
        warnings.append("dataset was not provided; schema validation was skipped")

    # 运行前依赖校验
    if registry is not None:
        checked: set[str] = set()
        config_by_computer = _parameter_config.resolve_parameter_computer_configs(
            ((configured.spec, configured.config) for configured in configured_operators),
            registry,
        )
        for node in graph.nodes:
            if node.node_type == "parameter" and node.computer_name is not None and node.computer_name not in checked:
                try:
                    computer = registry.get_parameter_computer(node.computer_name)
                    computer.before_run_check(config_by_computer.get(node.computer_name, ({}, "default"))[0])
                # 算子运行前检查是插件隔离边界，单个插件失败需要收集到 dry-run 结果。
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"before_run_check failed for {node.computer_name}: {exc}")
                checked.add(node.computer_name)

    estimated_artifacts = ["tables/parameter_table.parquet", "tables/evaluation_table.parquet"]
    for node in graph.nodes:
        if node.node_type == "parameter" and node.computer_name is not None:
            estimated_artifacts.append(f"artifacts/{node.computer_name}")
    preview_policies: dict[str, object] = {
        configured.operator_name: configured.spec.preview_policy for configured in configured_operators
    }
    return DryRunResult(
        selected_operators=[spec.spec.name for spec in configured_operators],
        expanded_selectors=[node.node_id.split(".", 1)[-1] for node in graph.nodes if node.node_type == "evaluation"],
        graph_nodes=[node.node_id for node in graph.nodes],
        policy_overrides={},
        warnings=warnings,
        errors=errors,
        estimated_artifacts=estimated_artifacts,
        preview_policies=preview_policies,
    )


def _coerce_run_id(run_options: Mapping[str, object], fallback: str | None = None) -> str:
    """从运行参数中提取 `run_id`，缺省时自动生成。"""
    raw = run_options.get("run_id")
    if isinstance(raw, str) and raw:
        return raw
    if fallback is not None:
        return fallback
    return uuid4().hex


def _coerce_retry_max_attempts(run_options: Mapping[str, object]) -> int:
    """解析 `retry_max_attempts`，保持兼容最小语义。"""
    raw = run_options.get("retry_max_attempts", 1)
    if raw is None:
        return 1
    if isinstance(raw, bool):
        raise TypeError("retry_max_attempts must be int or str")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, str):
        try:
            return int(raw)
        except ValueError as error:
            raise TypeError("retry_max_attempts must be int or str") from error
    raise TypeError("retry_max_attempts must be int or str")


def _coerce_sample_rule(run_options: Mapping[str, object]) -> dict[str, object] | None:
    """解析 sample 规则，并补齐确定性随机种子。"""
    raw = run_options.get("sample")
    if raw is None:
        return None
    if isinstance(raw, bool):
        raise TypeError("sample must be an integer or mapping")
    if isinstance(raw, int):
        rule: dict[str, object] = {"n": raw}
    elif isinstance(raw, Mapping):
        rule = {str(key): value for key, value in raw.items()}
    else:
        raise TypeError("sample must be an integer or mapping")

    size = rule.get("n")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ValueError("sample.n must be a positive integer")
    random_state = rule.get("random_state")
    if random_state is not None and (isinstance(random_state, bool) or not isinstance(random_state, int)):
        raise TypeError("sample.random_state must be an integer")
    return rule


def _complete_sample_rule(
    sample_rule: dict[str, object] | None,
    dataset: Dataset,
    graph: CleaningStateGraph,
) -> dict[str, object] | None:
    """为简写 sample 规则基于输入与计划补齐稳定随机种子。"""
    if sample_rule is None:
        return None
    if sample_rule.get("random_state") is not None:
        return sample_rule
    seed_material = f"{read_dataset_fingerprint(dataset)}:{graph.plan_hash}".encode()
    seed = int.from_bytes(sha256(seed_material).digest()[:8], "big") % (2**32)
    return {**sample_rule, "random_state": seed}


def _sample_dataset(dataset: Dataset, sample_rule: dict[str, object] | None, output_path: Path) -> Dataset:
    """按已归一化规则写入本 run 专属稳定样本 Dataset。"""
    if sample_rule is None:
        return dataset
    frame = normalize_identifier_columns(read_dataset_frame(dataset))
    raw_size = sample_rule["n"]
    raw_random_state = sample_rule["random_state"]
    if not isinstance(raw_size, int) or isinstance(raw_size, bool):
        raise TypeError("sample.n must be an integer")
    if not isinstance(raw_random_state, int) or isinstance(raw_random_state, bool):
        raise TypeError("sample.random_state must be an integer")
    sample_size = min(raw_size, len(frame))
    sampled = frame.sample(n=sample_size, random_state=raw_random_state).sort_index()
    storage = cast(Any, dataset).storage if hasattr(dataset, "storage") else None
    return Dataset.write(sampled, str(output_path), storage=storage)


def _coerce_label(run_options: Mapping[str, object]) -> str | None:
    """校验可选的运行标签。"""
    label = run_options.get("label")
    if label is None:
        return None
    if not isinstance(label, str) or not label:
        raise TypeError("label must be a non-empty string")
    return label


def _coerce_tags(run_options: Mapping[str, object]) -> list[str]:
    """校验可选的运行标签列表。"""
    tags = run_options.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag for tag in tags):
        raise TypeError("tags must be a list of non-empty strings")
    return list(tags)


def _coerce_progress_callback(run_options: Mapping[str, object]) -> Callable[[RuntimeEvent], None] | None:
    """解析 notebook/脚本运行时进度输出配置。"""
    raw = run_options.get("progress")
    if raw is None or raw is False:
        return None
    if raw == "auto" or raw is True:
        return _print_progress_event
    if callable(raw):
        return cast(Callable[[RuntimeEvent], None], raw)
    raise TypeError("progress must be None, 'auto', bool, or a RuntimeEvent callback")


def _print_progress_event(event: RuntimeEvent) -> None:
    """在 Notebook/终端中输出一行稳定的运行时进度。"""
    node = f" {event.node_id}" if event.node_id else ""
    message = f" - {event.message}" if event.message else ""
    print(f"[cleaner:{event.run_id}] {event.event_type}{node}{message}")


@dataclass(frozen=True)
class CleanerExecution:
    """清洗执行实例，承载编译图和运行时状态。"""

    graph: CleaningStateGraph
    registry: OperatorRegistry
    configured_operators: list[ConfiguredOperatorSpec]
    runtime: CleaningRuntime
    cache_root: Path
    node_policy: NodePolicy | None
    operator_policies: dict[str, NodePolicy] | None

    def __init__(
        self,
        graph: CleaningStateGraph,
        registry: OperatorRegistry,
        configured_operators: list[ConfiguredOperatorSpec],
        runtime: CleaningRuntime | None = None,
        cache_root: Path | None = None,
        node_policy: NodePolicy | None = None,
        operator_policies: dict[str, NodePolicy] | None = None,
    ) -> None:
        if cache_root is None:
            cache_root = _default_cache_root()
        if runtime is None:
            runtime = CleaningRuntime(cache_root, registry=registry)
        object.__setattr__(self, "graph", graph)
        object.__setattr__(self, "registry", registry)
        object.__setattr__(self, "configured_operators", configured_operators)
        object.__setattr__(self, "runtime", runtime)
        object.__setattr__(self, "cache_root", Path(cache_root))
        object.__setattr__(self, "node_policy", node_policy)
        object.__setattr__(self, "operator_policies", operator_policies)

    def plan(self) -> pd.DataFrame:
        """返回当前编译图的可视化计划。"""
        return self.graph.to_frame()

    def dry_run(self, dataset: Dataset | None = None) -> DryRunResult:
        """返回 dry-run 结果（当前只包含最小元信息）。"""
        return build_dry_run_result(self.graph, self.configured_operators, dataset, registry=self.registry)

    def run(self, dataset: Dataset, **run_options: object) -> CleanerResult:
        """按已编译图执行一次清洗运行。"""
        diagnostics = self.dry_run(dataset)
        if diagnostics.errors:
            raise ValueError("; ".join(diagnostics.errors))
        run_id = _coerce_run_id(run_options)
        sample_rule = _complete_sample_rule(_coerce_sample_rule(run_options), dataset, self.graph)
        progress_callback = _coerce_progress_callback(run_options)
        if progress_callback is None:
            runtime = self.runtime
        else:
            runtime = CleaningRuntime(
                self.cache_root,
                registry=self.registry,
                progress_callback=progress_callback,
            )
        runtime_dataset = _sample_dataset(
            dataset,
            sample_rule,
            runtime._cache_root / run_id / "input" / "sample.parquet",
        )
        runtime_result = runtime.run_graph(
            graph=self.graph,
            dataset=runtime_dataset,
            configured_operators=self.configured_operators,
            run_options=RunOptions(
                run_id=run_id,
                retry_max_attempts=_coerce_retry_max_attempts(run_options),
                sample_rule=sample_rule,
                label=_coerce_label(run_options),
                tags=_coerce_tags(run_options),
            ),
        )
        return CleanerResult(
            run_id=runtime_result.run_id,
            cache_root=runtime_result.cache_root,
            operator_preview_policies=self._preview_policies(),
            dataset=runtime_dataset,
        )

    def resume(
        self,
        *,
        dataset: Dataset,
        run_id: str | None = None,
        result: CleanerResult | None = None,
        sample: Mapping[str, object] | None = None,
    ) -> CleanerResult:
        """恢复历史运行并继续执行。"""
        if run_id is not None and result is not None and run_id != result.run_id:
            raise ValueError("run_id and result.run_id must match")
        runtime_run_id = run_id or (result.run_id if result is not None else None)
        runtime_result = self.runtime.resume_graph(
            graph=self.graph,
            dataset=dataset,
            run_id=runtime_run_id,
            result=result,
            configured_operators=self.configured_operators,
            sample_rule={str(key): value for key, value in sample.items()} if sample is not None else None,
        )
        return CleanerResult(
            run_id=runtime_result.run_id,
            cache_root=runtime_result.cache_root,
            operator_preview_policies=self._preview_policies(result),
            dataset=dataset,
        )

    def rerun(self, result: CleanerResult, operators: object, overwrite: bool = False) -> CleanerResult:
        """按结果做算子级重新运行（阶段1先返回最小壳）。"""
        configured_operators = select_operators(
            cast(OperatorSelectorInput, cast(OperatorConfigInput, operators)),
            self.registry,
        )
        rerun_graph = CleaningStateGraph.compile(
            configured_operators,
            self.registry,
            node_policy=self.node_policy,
            operator_policies=self.operator_policies,
        )
        runtime_result = self.runtime.rerun_evaluation(
            current_graph=self.graph,
            rerun_graph=rerun_graph,
            result=result,
            configured_operators=configured_operators,
            overwrite=overwrite,
        )
        return CleanerResult(
            run_id=runtime_result.run_id,
            cache_root=runtime_result.cache_root,
            operator_preview_policies=self._preview_policies(configured_operators=configured_operators),
            dataset=result._dataset,
        )

    def _preview_policies(
        self,
        result: CleanerResult | None = None,
        configured_operators: list[ConfiguredOperatorSpec] | None = None,
    ) -> dict[str, PreviewPolicy]:
        """按执行上下文构造可见的预览策略。"""
        if result is not None:
            return dict(result._operator_preview_policies)
        target = self.configured_operators if configured_operators is None else configured_operators
        return {spec.operator_name: spec.spec.preview_policy for spec in target}
