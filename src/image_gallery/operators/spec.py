from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

import pandas as pd

from image_gallery.cleaning.config import hash_config
from image_gallery.cleaning.preview_policy import PreviewPolicy


@dataclass(frozen=True)
class OperatorSpec:
    """逻辑算子规格，描述参数需求和评估输出契约。"""

    name: str
    category: str
    required_parameters: list[str]
    evaluation_columns: list[str]
    default_config: dict[str, object]
    action_column: str
    reason_column: str
    evaluator: Callable[[pd.DataFrame, dict[str, object]], pd.DataFrame]
    preview_policy: PreviewPolicy = field(default_factory=PreviewPolicy)

    def evaluate(self, parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
        """基于参数表和配置生成该算子的 evaluation 列。"""
        missing_parameters = [column for column in self.required_parameters if column not in parameter_table.columns]
        if missing_parameters:
            raise ValueError(f"missing required parameters for {self.name}: {missing_parameters}")

        result = self.evaluator(parameter_table.copy(), config)
        required_columns = ["image_id", *self.evaluation_columns]
        missing_columns = [column for column in required_columns if column not in result.columns]
        if missing_columns:
            raise ValueError(f"missing evaluation columns for {self.name}: {missing_columns}")
        return cast(pd.DataFrame, result[required_columns]).copy()


@dataclass(frozen=True)
class ConfiguredOperatorSpec:
    """已绑定并归一化的算子配置。"""

    spec: OperatorSpec
    config: dict[str, object]
    source: str
    operator_config_hash: str

    @property
    def operator_name(self) -> str:
        """返回算子名。"""
        return self.spec.name

    @classmethod
    def from_spec(
        cls,
        spec: OperatorSpec,
        config: dict[str, object],
        source: str,
    ) -> "ConfiguredOperatorSpec":
        """按 spec 的默认配置补齐，生成带稳定 hash 的已配置算子。"""
        merged_config = {**spec.default_config, **config}
        return cls(
            spec=spec,
            config=merged_config,
            source=source,
            operator_config_hash=hash_config(merged_config),
        )
