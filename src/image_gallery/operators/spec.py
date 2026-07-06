from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd


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
        return result[required_columns].copy()
