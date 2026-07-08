from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from image_gallery.cleaning.config import OperatorConfigInput
from image_gallery.cleaning.preview import PreviewResult
from image_gallery.dataset import Dataset


class Cleaner(ABC):
    """清洗策略基类。"""

    @abstractmethod
    def compile(self) -> "Cleaner":
        """编译当前 Cleaner 配置，不读取 dataset，不写运行产物。"""

    @abstractmethod
    def plan(self) -> pd.DataFrame:
        """返回当前编译计划的可读表格。"""

    @abstractmethod
    def run(
        self,
        dataset: Dataset,
        output_dir: str | Path | None = None,
        overwrite: bool = False,
    ) -> "Cleaner":
        """执行当前 Cleaner 配置的全部算子。"""

    @abstractmethod
    def preview(self, limit: int = 20) -> PreviewResult:
        """预览当前 evaluation_table 的清洗结果。"""

    @abstractmethod
    def state(self) -> pd.DataFrame:
        """返回每个算子的运行状态矩阵。"""

    @abstractmethod
    def config(self, operator_configs: OperatorConfigInput) -> "Cleaner":
        """更新一个或多个算子的配置，不主动重算。"""

    @abstractmethod
    def rerun(self, operator_configs: OperatorConfigInput) -> "Cleaner":
        """按传入配置重新计算一个或多个算子。"""

    @abstractmethod
    def result(self, operator_name: str) -> pd.DataFrame:
        """返回指定算子的评估结果列。"""

    @abstractmethod
    def export(self, kind: str, path: str) -> Dataset:
        """导出指定结果视图。"""
