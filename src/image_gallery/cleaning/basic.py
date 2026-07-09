from __future__ import annotations

from pathlib import Path
from typing import cast

import pandas as pd

from image_gallery.cleaning.cleaner import Cleaner
from image_gallery.cleaning.config import OperatorConfigInput
from image_gallery.cleaning.errors import CleanerStateError
from image_gallery.cleaning.execution import CleanerExecution, _default_cache_root
from image_gallery.cleaning.graph import CleaningStateGraph
from image_gallery.cleaning.policy import NodePolicy
from image_gallery.cleaning.preview import PreviewResult
from image_gallery.cleaning.result import CleanerResult
from image_gallery.cleaning.selection import OperatorSelectorInput, select_operators
from image_gallery.dataset import Dataset
from image_gallery.operators.builtin import create_default_registry
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.semantic_provider import SemanticEmbeddingProvider


class BasicCleaner(Cleaner):
    """BasicCleaner 作为清洗编译器与运行入口。"""

    def __init__(
        self,
        operator_configs: OperatorConfigInput,
        output_dir: str | Path | None = None,
        registry: OperatorRegistry | None = None,
        semantic_providers: dict[str, SemanticEmbeddingProvider] | None = None,
        node_policy: NodePolicy | None = None,
        operator_policies: dict[str, NodePolicy] | None = None,
    ) -> None:
        self._operators: OperatorSelectorInput = cast(OperatorSelectorInput, operator_configs)
        self._registry = registry if registry is not None else create_default_registry(semantic_providers)
        self._cache_root = Path(output_dir) if output_dir is not None else None
        self._node_policy = node_policy
        self._operator_policies = operator_policies

    def compile(self) -> CleanerExecution:
        """编译当前算子配置并返回运行执行实例。"""
        configured = select_operators(
            self._operators,
            self._registry,
        )
        graph = CleaningStateGraph.compile(
            configured,
            self._registry,
            node_policy=self._node_policy,
            operator_policies=self._operator_policies,
        )
        return CleanerExecution(
            graph=graph,
            registry=self._registry,
            configured_operators=configured,
            cache_root=self._cache_root or _default_cache_root(),
            node_policy=self._node_policy,
            operator_policies=self._operator_policies,
        )

    def plan(self) -> pd.DataFrame:
        """返回当前编译计划 DataFrame。"""
        return self.compile().plan()

    def run(self, dataset: Dataset, **run_options: object) -> CleanerResult:
        """执行清洗图并返回运行结果。"""
        if not isinstance(dataset, Dataset):
            raise CleanerStateError("dataset must be a Dataset instance")
        return self.compile().run(dataset, **run_options)

    def preview(self, limit: int = 20) -> PreviewResult:
        """阶段性结果预览：Task7 提供正式实现。"""
        del limit
        raise NotImplementedError("preview is implemented in task7")

    def preview_html(
        self,
        path: str | Path,
        *,
        action: str | None = None,
        filters: dict[str, object] | None = None,
        groupby: str | None = None,
        include_group_context: bool = False,
        sort_by: list[str] | None = None,
        ascending: bool | list[bool] = True,
        caption_columns: list[str] | None = None,
        max_rows: int = 200,
        max_groups: int = 50,
        max_items_per_group: int = 20,
        thumbnail_size: int = 320,
        columns_per_row: int = 6,
    ) -> Path:
        """阶段性 HTML 预览：Task7 提供正式实现。"""
        del path
        del action
        del filters
        del groupby
        del include_group_context
        del sort_by
        del ascending
        del caption_columns
        del max_rows
        del max_groups
        del max_items_per_group
        del thumbnail_size
        del columns_per_row
        raise NotImplementedError("preview_html is implemented in task7")

    def state(self) -> pd.DataFrame:
        """返回算子运行状态：Task7 提供正式实现。"""
        raise NotImplementedError("state is implemented in task7")

    def config(self, operator_configs: OperatorConfigInput) -> BasicCleaner:
        """更新算子配置，下一次编译将基于新配置。"""
        self._operators = cast(OperatorSelectorInput, operator_configs)
        return self

    def rerun(self, operator_configs: OperatorConfigInput) -> BasicCleaner:
        """按新配置重跑。"""
        del operator_configs
        raise NotImplementedError("rerun is implemented in task7")

    def result(self, operator_name: str) -> pd.DataFrame:
        """返回算子执行结果：Task7 提供正式实现。"""
        del operator_name
        raise NotImplementedError("result is implemented in task7")

    def export(self, kind: str, path: str) -> Dataset:
        """导出结果：Task7 提供正式实现。"""
        del kind
        del path
        raise NotImplementedError("export is implemented in task7")
