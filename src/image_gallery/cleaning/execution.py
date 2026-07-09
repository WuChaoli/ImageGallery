"""Execution layer for cleaner lifecycle."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

import pandas as pd

from image_gallery.cleaning.graph import CleaningStateGraph
from image_gallery.cleaning.result import CleanerResult
from image_gallery.cleaning.runtime import CleaningRuntime, RunOptions
from image_gallery.dataset import Dataset
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import ConfiguredOperatorSpec


def _default_cache_root() -> Path:
    """返回默认清洗运行时缓存目录。"""
    return Path(gettempdir()) / "image-gallery-cleaning-runtime"


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
    _dataset: Dataset | None = None,
) -> DryRunResult:
    """构建 `dry_run` 结果。"""
    del _dataset
    return DryRunResult(
        selected_operators=[spec.spec.name for spec in configured_operators],
        expanded_selectors=[node.node_id.split(".", 1)[-1] for node in graph.nodes if node.node_type == "evaluation"],
        graph_nodes=[node.node_id for node in graph.nodes],
        policy_overrides={},
        warnings=[],
        errors=[],
        estimated_artifacts=[],
        preview_policies={},
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


@dataclass(frozen=True)
class CleanerExecution:
    """清洗执行实例，承载编译图和运行时状态。"""

    graph: CleaningStateGraph
    registry: OperatorRegistry
    configured_operators: list[ConfiguredOperatorSpec]
    runtime: CleaningRuntime
    cache_root: Path

    def __init__(
        self,
        graph: CleaningStateGraph,
        registry: OperatorRegistry,
        configured_operators: list[ConfiguredOperatorSpec],
        runtime: CleaningRuntime | None = None,
        cache_root: Path | None = None,
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

    def plan(self) -> pd.DataFrame:
        """返回当前编译图的可视化计划。"""
        return self.graph.to_frame()

    def dry_run(self, dataset: Dataset | None = None) -> DryRunResult:
        """返回 dry-run 结果（当前只包含最小元信息）。"""
        return build_dry_run_result(self.graph, self.configured_operators, dataset)

    def run(self, dataset: Dataset, **run_options: object) -> CleanerResult:
        """按已编译图执行一次清洗运行。"""
        runtime_result = self.runtime.run_graph(
            graph=self.graph,
            dataset=dataset,
            configured_operators=self.configured_operators,
            run_options=RunOptions(
                run_id=_coerce_run_id(run_options),
                retry_max_attempts=_coerce_retry_max_attempts(run_options),
            ),
        )
        return CleanerResult(run_id=runtime_result.run_id, cache_root=runtime_result.cache_root)

    def resume(
        self,
        *,
        dataset: Dataset,
        run_id: str | None = None,
        result: CleanerResult | None = None,
    ) -> CleanerResult:
        """恢复历史运行并继续执行。"""
        runtime_run_id = run_id or (result.run_id if result is not None else None)
        runtime_result = self.runtime.resume_graph(
            graph=self.graph,
            dataset=dataset,
            run_id=runtime_run_id,
        )
        return CleanerResult(run_id=runtime_result.run_id, cache_root=runtime_result.cache_root)

    def rerun(self, result: CleanerResult, operators: object, overwrite: bool = False) -> CleanerResult:
        """按结果做算子级重新运行（阶段1先返回最小壳）。"""
        del operators
        del overwrite
        runtime_result = self.runtime.rerun_evaluation(self.graph, result)
        return CleanerResult(run_id=runtime_result.run_id, cache_root=runtime_result.cache_root)
