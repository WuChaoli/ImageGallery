from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from image_gallery.dataset.dataset import Dataset


@dataclass(frozen=True)
class DatasetExportResult:
    """Dataset 导出结果摘要，供目录型和文件型 exporter 共用。"""

    output_dir: str | None = None
    output_path: str | None = None
    image_count: int = 0
    annotation_count: int = 0
    failures: list[dict[str, object]] = field(default_factory=list)


@runtime_checkable
class DatasetLoader(Protocol):
    """把外部资源加载为 Dataset 的协议。"""

    def load(self) -> Dataset:
        """加载外部资源并返回 Dataset。"""
        ...


@runtime_checkable
class DatasetExporter(Protocol):
    """把 Dataset 导出到外部资源的协议。"""

    def export(self, dataset: Dataset) -> DatasetExportResult:
        """导出 Dataset 并返回结果摘要。"""
        ...
