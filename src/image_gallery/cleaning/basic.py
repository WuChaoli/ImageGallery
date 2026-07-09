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
from image_gallery.cleaning.result import CleanerResult
from image_gallery.cleaning.selection import OperatorOverrides, OperatorSelectorInput, select_operators
from image_gallery.cleaning.toml_config import CleanerConfig, build_cleaner_toml_template
from image_gallery.dataset import Dataset
from image_gallery.operators.builtin import create_default_registry
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.semantic_provider import SemanticEmbeddingProvider


class BasicCleaner(Cleaner):
    """BasicCleaner 作为清洗编译器与运行入口。"""

    def __init__(
        self,
        operator_configs: OperatorSelectorInput,
        output_dir: str | Path | None = None,
        registry: OperatorRegistry | None = None,
        semantic_providers: dict[str, SemanticEmbeddingProvider] | None = None,
        node_policy: NodePolicy | None = None,
        operator_policies: dict[str, NodePolicy] | None = None,
        operator_config_overrides: OperatorOverrides = None,
    ) -> None:
        self._operators = operator_configs
        self._operator_config_overrides = operator_config_overrides
        self._registry = registry if registry is not None else create_default_registry(semantic_providers)
        self._cache_root = Path(output_dir) if output_dir is not None else None
        self._node_policy = node_policy
        self._operator_policies = operator_policies

    @classmethod
    def from_config(cls, config: CleanerConfig) -> BasicCleaner:
        """从 CleanerConfig 构造 BasicCleaner。"""
        return cls(
            config.operators,
            node_policy=config.node_policy,
            operator_policies=config.operator_policies,
            operator_config_overrides=config.operator_configs,
        )

    @classmethod
    def from_toml(cls, path: str | Path) -> BasicCleaner:
        """从 TOML 配置构造 BasicCleaner。"""
        return cls.from_config(CleanerConfig.from_toml(path))

    @classmethod
    def export_config_template(cls, path: str | Path, operators: object) -> Path:
        """导出不含密钥的 cleaner TOML 模板。"""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(build_cleaner_toml_template(operators), encoding="utf-8")
        return output_path

    def compile(self) -> CleanerExecution:
        """编译当前算子配置并返回运行执行实例。"""
        configured = select_operators(
            self._operators,
            self._registry,
            overrides=self._operator_config_overrides,
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

    def config(self, operator_configs: OperatorConfigInput) -> BasicCleaner:
        """更新算子配置，下一次编译将基于新配置。"""
        self._operators = cast(OperatorSelectorInput, operator_configs)
        self._operator_config_overrides = None
        return self
