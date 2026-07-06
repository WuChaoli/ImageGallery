from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pandas as pd
from PIL import Image


class ComputeStage(str, Enum):
    """参数计算阶段。"""

    IMAGE_BATCH = "image_batch"
    TABLE_DERIVED = "table_derived"
    DATASET_GLOBAL = "dataset_global"


@dataclass(frozen=True)
class ImageBatchItem:
    """Cleaner 统一读取和解码后的单张图片上下文。"""

    image_id: str
    image_uri: str
    row: dict[str, object]
    data: bytes | None
    image: Image.Image | None
    error: str | None


@dataclass(frozen=True)
class ImageBatch:
    """同一批图片的共享读取和解码上下文。"""

    items: list[ImageBatchItem]


@dataclass(frozen=True)
class ParameterRequest:
    """一次参数计算请求。"""

    parameter_table: pd.DataFrame
    requested_parameters: frozenset[str]
    config: dict[str, object]
    config_hash: str
    artifacts_dir: Path
    image_batch: ImageBatch | None = None


@dataclass(frozen=True)
class ParameterResult:
    """参数计算结果。"""

    parameter_updates: pd.DataFrame
    relation_updates: dict[str, pd.DataFrame]
    artifact_refs: dict[str, str]
    parameter_manifest: dict[str, dict[str, object]]


class ParameterComputer(ABC):
    """参数计算单元基类。"""

    name: str
    stage: ComputeStage
    produced_parameters: frozenset[str]

    @abstractmethod
    def compute(self, request: ParameterRequest) -> ParameterResult:
        """按请求批量生产参数列。"""
