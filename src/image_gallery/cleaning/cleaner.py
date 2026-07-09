from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from image_gallery.cleaning.config import OperatorConfigInput
from image_gallery.cleaning.preview import PreviewResult
from image_gallery.dataset import Dataset


class Cleaner(ABC):
    """清洗策略基类。"""

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
    def preview(self, limit: int = 20) -> PreviewResult:
        """预览当前 evaluation_table 的清洗结果。"""

    @abstractmethod
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
        """把当前清洗结果写出为静态 HTML 预览页。"""

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
