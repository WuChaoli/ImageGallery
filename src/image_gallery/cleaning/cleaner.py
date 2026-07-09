from abc import ABC, abstractmethod

import pandas as pd

from image_gallery.cleaning.config import OperatorConfigInput
from image_gallery.dataset import Dataset


class Cleaner(ABC):
    """清洗构建器基类。"""

    @abstractmethod
    def compile(self) -> object:
        """编译当前 Cleaner 配置，不读取 dataset，不写运行产物。"""

    @abstractmethod
    def plan(self) -> pd.DataFrame:
        """返回当前编译计划的可读表格。"""

    @abstractmethod
    def run(
        self,
        dataset: Dataset,
        **run_options: object,
    ) -> object:
        """执行当前 Cleaner 配置的全部算子。"""

    @abstractmethod
    def config(self, operator_configs: OperatorConfigInput) -> "Cleaner":
        """更新一个或多个算子的配置，不主动重算。"""
