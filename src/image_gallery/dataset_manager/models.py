"""DatasetManager 领域对象的公共句柄。"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pandas as pd

from image_gallery.dataset_manager._physical_schema import ColumnSpec, FieldType

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

    @property
    def dataset(self) -> Dataset:
        """按不可变 ID 返回所属 Dataset 句柄。"""
        return self._manager._view_owner_dataset(view=self)

    @property
    def repo(self) -> DatasetRepo:
        """按不可变 ID 返回所属 DatasetRepo 句柄。"""
        return self._manager._view_owner_repo(view=self)

    def scan(self, *, fields: list[str] | None = None) -> pd.DataFrame:
        """以 DataFrame 读取固定 Snapshot，可组合 Repo 当前向量。"""
        return self._manager._scan_view_frame(view=self, fields=fields)

    def count(self) -> int:
        """返回固定 Snapshot 的行数。"""
        return len(self.scan().index)

    def preview(self, *, limit: int = 10) -> pd.DataFrame:
        """返回固定 Snapshot 的前若干行。"""
        return self.scan().head(limit)

    def read_image(self, *, asset_id: str) -> bytes:
        """通过行内位置委托 StorageManager 读取图片。"""
        return self._manager._read_view_image(view=self, asset_id=asset_id)

    def verify_image(self, *, asset_id: str) -> bool:
        """重新读取图片并显式验证行内内容身份。"""
        return self._manager._verify_view_image(view=self, asset_id=asset_id)

    def get_row(  # pyright: ignore[reportMissingTypeArgument, reportUnknownParameterType]
        self, *, asset_id: str, fields: list[str] | None = None
    ) -> pd.Series:
        """按 asset_id 返回固定 Snapshot 中的完整行。"""
        return self._manager._get_view_row_series(view=self, asset_id=asset_id, fields=fields)

    def get_rows(self, *, asset_ids: list[str], fields: list[str] | None = None) -> pd.DataFrame:
        """按 asset_id 批量返回 DataFrame。"""
        selected = fields
        if selected is not None and "asset_id" not in selected:
            selected = ["asset_id", *selected]
        frame = self.scan(fields=selected)
        matched = cast(pd.DataFrame, frame[frame["asset_id"].isin(asset_ids)]).reset_index(drop=True)
        if fields is not None and "asset_id" not in fields:
            matched = cast(pd.DataFrame, matched.loc[:, fields])
        return matched

    def iter_images(self) -> Iterator[tuple[dict[str, object], bytes]]:
        """逐行返回位置元数据与 StorageManager 图片 bytes。"""
        for row in self._manager._scan_view(view=self, columns=None):
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
class VectorField:
    """表示锁定到一套向量空间和验证集的 Repo 字段。"""

    vector_field_id: str
    repo_id: str
    name: str
    model_id: str
    model_fingerprint: str
    dimension: int
    numeric_type: str
    distance: str
    _manager: DatasetManager

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
        frame: pd.DataFrame,
        fields: list[str] | None = None,
    ) -> CommitResult:
        """以完整行 upsert 推进目标 Branch。"""
        return self._manager._commit(
            dataset=self,
            branch=branch,
            base=base,
            frame=frame,
            fields=fields,
        )

    @property
    def schema(self) -> DatasetSchema:
        """返回 Dataset 物理 Schema facade。"""
        return DatasetSchema(self)

    def generate_embed(
        self,
        *,
        field: str,
        source: DatasetView | None = None,
        branch: str = "main",
        overwrite: bool = False,
    ) -> EmbedResult:
        """为默认 Branch Head 或精确 View 生成 Repo 当前向量。"""
        return self._manager._generate_embed(
            dataset=self,
            field_name=field,
            source=source,
            branch=branch,
            overwrite=overwrite,
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
        """从同 Dataset 的固定 View 创建新 Branch。"""
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

    @property
    def schema(self) -> RepoSchema:
        """返回 Repo Vector Schema facade。"""
        return RepoSchema(self)

    def create_tag(
        self,
        *,
        name: str,
        color: str | None = None,
        description: str | None = None,
    ) -> TagDefinition:
        """创建 Repo 级 Tag Definition。"""
        return self._manager._create_tag(repo=self, name=name, color=color, description=description)

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


@dataclass(frozen=True, slots=True)
class EmbedResult:
    """描述一次 Dataset 范围的向量生成结果。"""

    source_snapshot_id: int | None
    generated: int
    updated: int
    skipped: int


@dataclass(frozen=True, slots=True)
class DatasetSchema:
    """提供 Dataset 物理列操作。"""

    dataset: Dataset

    def add_column(
        self,
        *,
        branch: str,
        base: DatasetView,
        column: ColumnSpec | None = None,
        name: str | None = None,
        field_type: FieldType | str | None = None,
    ) -> DatasetView:
        """向目标 Branch 新增可选普通列。"""
        return self.dataset._manager._add_column(
            dataset=self.dataset,
            branch=branch,
            base=base,
            column=column,
            name=name,
            field_type=field_type,
        )

    def list_columns(self) -> list[ColumnSpec]:
        """按物理顺序返回 typed 列定义。"""
        return self.dataset._manager._list_columns(dataset=self.dataset)

    def get_column(self, *, name: str) -> ColumnSpec:
        """按精确名称返回 typed 物理列定义。"""
        for column in self.list_columns():
            if column.name == name:
                return column
        raise KeyError(name)


@dataclass(frozen=True, slots=True)
class RepoSchema:
    """提供 Repo VectorField 操作。"""

    repo: DatasetRepo

    def add_vector(self, *, name: str, model_id: str, distance: str) -> VectorField:
        """创建强绑定冻结模型的 VectorField。"""
        return self.repo._manager._create_bound_vector_field(
            repo=self.repo, name=name, model_id=model_id, distance=distance
        )

    def get_vector(self, *, name: str) -> VectorField:
        """按名称返回 VectorField。"""
        return self.repo._manager._open_vector_field(repo=self.repo, name=name)

    def list_vectors(self) -> list[VectorField]:
        """返回 Repo 全部 VectorField。"""
        return self.repo._manager._list_vector_fields(repo=self.repo)
