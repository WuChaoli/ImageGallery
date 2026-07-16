"""DatasetManager 领域对象的公共句柄。"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from image_gallery.dataset_manager.manager import DatasetManager


@dataclass(frozen=True, slots=True)
class DatasetView:
    """表示固定到精确 Iceberg Snapshot 的只读数据集视图。"""

    repo_id: str
    dataset_id: str
    snapshot_id: int | None
    ref_name: str
    ref_type: str
    _manager: DatasetManager

    def scan(self, *, columns: list[str] | None = None) -> list[dict[str, object]]:
        """读取固定 Snapshot 的精确列投影。"""
        return self._manager._scan_view(view=self, columns=columns)

    def count(self) -> int:
        """返回固定 Snapshot 的行数。"""
        return len(self.scan())

    def preview(self, *, limit: int = 10) -> list[dict[str, object]]:
        """返回固定 Snapshot 的前若干行。"""
        return self.scan()[:limit]

    def read_image(self, *, asset_id: str) -> bytes:
        """通过行内位置委托 StorageManager 读取图片。"""
        return self._manager._read_view_image(view=self, asset_id=asset_id)

    def verify_image(self, *, asset_id: str) -> bool:
        """重新读取图片并显式验证行内内容身份。"""
        return self._manager._verify_view_image(view=self, asset_id=asset_id)

    def get_row(self, *, asset_id: str) -> dict[str, object]:
        """按 asset_id 返回固定 Snapshot 中的完整行。"""
        return self._manager._get_view_row(view=self, asset_id=asset_id)

    def iter_images(self) -> Iterator[tuple[dict[str, object], bytes]]:
        """逐行返回位置元数据与 StorageManager 图片 bytes。"""
        for row in self.scan():
            yield row, self.read_image(asset_id=str(row["asset_id"]))


@dataclass(frozen=True, slots=True)
class CommitResult:
    """描述一次 Dataset Commit 的可见结果。"""

    view: DatasetView
    inserted: int
    updated: int
    changed: bool


@dataclass(frozen=True, slots=True)
class TagDefinition:
    """描述 DatasetRepo 级 Tag Definition。"""

    tag_id: str
    repo_id: str
    name: str
    color: str | None
    description: str | None
    archived: bool


@dataclass(frozen=True, slots=True)
class VectorValidationItem:
    """描述固定验证输入及其预期向量。"""

    probe: bytes
    expected: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class VectorWriteResult:
    """描述一次 Repo 当前向量写入。"""

    inserted: int
    updated: int
    skipped: int


@dataclass(frozen=True, slots=True)
class VectorCommit:
    """描述随 Dataset Commit 原子发布的一组调用方向量。"""

    field: VectorField
    items: dict[str, tuple[float, ...]]
    validation_outputs: list[tuple[float, ...]]
    overwrite: bool = False


@dataclass(frozen=True, slots=True)
class VectorField:
    """表示锁定到一套向量空间和验证集的 Repo 字段。"""

    vector_field_id: str
    repo_id: str
    name: str
    dimension: int
    numeric_type: str
    distance: str
    tolerance: float
    validation_set: tuple[VectorValidationItem, ...]
    _manager: DatasetManager

    def write(
        self,
        *,
        source: DatasetView,
        items: dict[str, tuple[float, ...]],
        validation_outputs: list[tuple[float, ...]],
        overwrite: bool = False,
    ) -> VectorWriteResult:
        """验证来源 View 和完整验证集后写入 Repo 当前向量。"""
        return self._manager._write_vectors(
            field=self,
            source=source,
            items=items,
            validation_outputs=validation_outputs,
            overwrite=overwrite,
        )

    def get(self, *, asset_id: str) -> tuple[float, ...] | None:
        """按内容身份读取 Repo 当前向量。"""
        return self._manager._get_vector(field=self, asset_id=asset_id)


@dataclass(frozen=True, slots=True)
class Dataset:
    """表示由 DatasetRepo 管理的单表 Iceberg 数据集。"""

    repo_id: str
    dataset_id: str
    name: str
    table_identifier: str
    _manager: DatasetManager

    def open_branch(self, *, name: str = "main") -> DatasetView:
        """打开固定到当前 Branch Head 的只读 View。"""
        return self._manager._open_branch(dataset=self, name=name)

    def commit(
        self,
        *,
        branch: str,
        base: DatasetView,
        rows: list[dict[str, object]],
        vectors: list[VectorCommit] | None = None,
    ) -> CommitResult:
        """以完整行 upsert 推进目标 Branch。"""
        return self._manager._commit(
            dataset=self,
            branch=branch,
            base=base,
            rows=rows,
            vectors=vectors,
        )

    def add_column(
        self,
        *,
        branch: str,
        base: DatasetView,
        name: str,
        field_type: str,
    ) -> DatasetView:
        """以精确 Branch 基线新增可选业务列。"""
        return self._manager._add_column(
            dataset=self,
            branch=branch,
            base=base,
            name=name,
            field_type=field_type,
        )

    def create_checkpoint(self, *, name: str, source: DatasetView) -> DatasetView:
        """从精确 View 创建不可变 Checkpoint。"""
        return self._manager._create_checkpoint(dataset=self, name=name, source=source)

    def open_checkpoint(self, *, name: str) -> DatasetView:
        """打开不可变 Checkpoint View。"""
        return self._manager._open_checkpoint(dataset=self, name=name)

    def list_checkpoints(self) -> list[str]:
        """列出 Dataset 的公开历史 Checkpoint。"""
        return self._manager._list_checkpoints(dataset=self)

    def create_branch(self, *, name: str, source: DatasetView) -> DatasetView:
        """从 Checkpoint 创建新 Branch。"""
        return self._manager._create_branch(dataset=self, name=name, source=source)

    def rollback(self, *, branch: str, base: DatasetView, checkpoint: DatasetView) -> DatasetView:
        """把 Branch 回退到同 lineage 的祖先 Checkpoint。"""
        return self._manager._rollback(dataset=self, branch=branch, base=base, checkpoint=checkpoint)


@dataclass(frozen=True, slots=True)
class DatasetRepo:
    """表示 Dataset、Tag 和 Vector 的硬隔离边界。"""

    repo_id: str
    name: str
    namespace: str
    _manager: DatasetManager

    def create_dataset(self, *, name: str) -> Dataset:
        """在 Repo 中创建单表 Dataset。"""
        return self._manager._create_dataset(repo=self, name=name)

    def open_dataset(self, *, name: str) -> Dataset:
        """按大小写不敏感名称打开 Dataset。"""
        return self._manager._open_dataset(repo=self, name=name)

    def list_datasets(self) -> list[Dataset]:
        """按名称返回 Repo 中全部 Dataset。"""
        return self._manager._list_datasets(repo=self)

    def bind_storage_prefix(self, *, prefix_id: str) -> None:
        """授权本 Repo 使用 Storage Prefix。"""
        self._manager._bind_storage_prefix(repo=self, prefix_id=prefix_id)

    def list_storage_prefix_ids(self) -> list[str]:
        """返回 Repo 已授权 Storage Prefix ID。"""
        return self._manager._list_storage_prefix_ids(repo=self)

    def create_tag(
        self,
        *,
        name: str,
        color: str | None = None,
        description: str | None = None,
    ) -> TagDefinition:
        """创建 Repo 级 Tag Definition。"""
        return self._manager._create_tag(repo=self, name=name, color=color, description=description)

    def create_vector_field(
        self,
        *,
        name: str,
        dimension: int,
        numeric_type: str = "float32",
        distance: str,
        validation_set: list[VectorValidationItem],
        tolerance: float = 1e-6,
    ) -> VectorField:
        """原子创建锁定的 Repo VectorField。"""
        return self._manager._create_vector_field(
            repo=self,
            name=name,
            dimension=dimension,
            numeric_type=numeric_type,
            distance=distance,
            validation_set=validation_set,
            tolerance=tolerance,
        )

    def open_vector_field(self, *, name: str) -> VectorField:
        """按大小写不敏感名称打开 VectorField。"""
        return self._manager._open_vector_field(repo=self, name=name)

    def get_vector_field(self, *, vector_field_id: str) -> VectorField:
        """按不可变 ID 返回 Repo VectorField。"""
        return self._manager._get_vector_field(repo=self, vector_field_id=vector_field_id)

    def list_vector_fields(self) -> list[VectorField]:
        """按名称返回 Repo 全部 VectorField。"""
        return self._manager._list_vector_fields(repo=self)

    def rename_tag(self, *, tag_id: str, name: str) -> TagDefinition:
        """重命名 Tag Definition，不改写 Dataset 行。"""
        return self._manager._rename_tag(repo=self, tag_id=tag_id, name=name)

    def archive_tag(self, *, tag_id: str) -> TagDefinition:
        """归档 Tag Definition 并禁止新增 Assignment。"""
        return self._manager._archive_tag(repo=self, tag_id=tag_id)

    def clone_dataset(self, *, source: DatasetView, name: str) -> Dataset:
        """从同 Repo 精确 View 克隆当前状态，不继承历史。"""
        return self._manager._clone_dataset(repo=self, source=source, name=name)
