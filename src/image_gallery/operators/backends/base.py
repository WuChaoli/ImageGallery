from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from image_gallery.dataset import Dataset


@dataclass(frozen=True)
class BackendOperatorRequest:
    """传给后端的单个逻辑算子参数计算请求。"""

    operator_name: str
    parameter_columns: list[str]
    config: dict[str, object]
    config_hash: str


@dataclass(frozen=True)
class BackendResult:
    """后端计算结果。"""

    parameter_updates: pd.DataFrame
    relation_updates: dict[str, pd.DataFrame]
    artifact_refs: dict[str, str]


class BackendAdapter(ABC):
    """物理后端 adapter 基类。"""

    name: str

    @abstractmethod
    def compute_parameters(
        self,
        dataset: "Dataset",
        parameter_table: pd.DataFrame,
        requests: list[BackendOperatorRequest],
        artifacts_dir: str | Path,
    ) -> BackendResult:
        """按一组逻辑算子请求批量计算参数字段。"""
