"""固定 DatasetView 物理行与 Repo 当前向量的私有 IO 组件。"""

from __future__ import annotations

from typing import cast

import pandas as pd
from pyiceberg.catalog import Catalog

from image_gallery.dataset_manager._repository_store import DatasetRecord, RepositoryStore
from image_gallery.dataset_manager._vector_store import VectorStore
from image_gallery.dataset_manager.errors import ObjectNotFoundError, ValidationError
from image_gallery.dataset_manager.models import DatasetView
from image_gallery.storage_manager import StorageManager, StoredObject


class ViewIO:
    """读取固定 Snapshot 物理行并按需合并 Repo 当前向量。"""

    def __init__(
        self,
        *,
        catalog: Catalog,  # pyright: ignore[reportUnknownParameterType]
        storage_manager: StorageManager,
        repositories: RepositoryStore,
        vectors: VectorStore,
    ) -> None:
        """绑定 View 读取所需的最小后端依赖。"""
        self._catalog = catalog
        self._storage_manager = storage_manager
        self._repositories = repositories
        self._vectors = vectors

    def scan(self, *, view: DatasetView, columns: list[str] | None) -> list[dict[str, object]]:
        """从 View 固定 Snapshot 扫描指定物理列。"""
        dataset = self._dataset(view=view)
        table = self._catalog.load_table(dataset.table_identifier)
        current_columns = [field.name for field in table.schema().fields]
        known_columns = set(current_columns)
        requested = current_columns if columns is None else columns
        if not set(requested).issubset(known_columns):
            raise ValidationError("Unknown Physical Schema column")
        if view.snapshot_id is None:
            return []
        snapshot = table.snapshot_by_id(view.snapshot_id)
        if snapshot is None:
            raise ObjectNotFoundError(str(view.snapshot_id))
        snapshot_schema_id = snapshot.schema_id
        if snapshot_schema_id is None:
            raise ObjectNotFoundError(f"Snapshot Schema: {view.snapshot_id}")
        snapshot_schema = table.schemas().get(snapshot_schema_id)
        if snapshot_schema is None:
            raise ObjectNotFoundError(f"Snapshot Schema: {snapshot_schema_id}")
        snapshot_columns = {field.name for field in snapshot_schema.fields}
        available = [name for name in requested if name in snapshot_columns]
        query_columns = available or ["asset_id"]
        stored_rows = cast(
            list[dict[str, object]],
            table.scan(snapshot_id=view.snapshot_id, selected_fields=tuple(query_columns)).to_arrow().to_pylist(),
        )
        # Schema 是 Table 级；固定旧 Snapshot 对后来新增的 optional 列补 null。
        return [{name: row.get(name) for name in requested} for row in stored_rows]

    def scan_frame(self, *, view: DatasetView, fields: list[str] | None) -> pd.DataFrame:
        """按调用方字段顺序返回物理列和显式 Repo 当前向量。"""
        dataset = self._dataset(view=view)
        table = self._catalog.load_table(dataset.table_identifier)
        physical = [field.name for field in table.schema().fields]
        vectors = {record.name: record for record in self._vectors.list(repo_id=view.repo_id)}
        selected = fields or physical
        unknown = set(selected) - set(physical) - set(vectors)
        if unknown:
            raise ValidationError(f"Unknown fields: {sorted(unknown)}")
        physical_selected = [name for name in selected if name in physical]
        query_columns = list(dict.fromkeys(["asset_id", *physical_selected]))
        rows = self.scan(view=view, columns=query_columns)
        frame = pd.DataFrame(rows, columns=query_columns)
        vector_selected = [name for name in selected if name in vectors]
        for name in vector_selected:
            frame[name] = None
        if vector_selected and not frame.empty:
            asset_ids = cast(pd.Series, frame["asset_id"]).astype(str).tolist()
            for name in vector_selected:
                field = vectors[name]
                mapping = self._vectors.list_current(
                    repo_id=view.repo_id,
                    vector_field_id=field.vector_field_id,
                    asset_ids=asset_ids,
                )
                frame[name] = cast(pd.Series, frame["asset_id"]).map(mapping).astype(object)
                frame[name] = cast(pd.Series, frame[name]).where(cast(pd.Series, frame[name]).notna(), None)
        return cast(pd.DataFrame, frame.loc[:, selected]).reset_index(drop=True)

    def get_row_series(  # pyright: ignore[reportMissingTypeArgument, reportUnknownParameterType]
        self,
        *,
        view: DatasetView,
        asset_id: str,
        fields: list[str] | None,
    ) -> pd.Series:
        """按 asset_id 返回固定 View 的一行并保持字段投影。"""
        selected = fields
        if selected is not None and "asset_id" not in selected:
            selected = ["asset_id", *selected]
        frame = self.scan_frame(view=view, fields=selected)
        matched = cast(pd.DataFrame, frame[cast(pd.Series, frame["asset_id"]) == asset_id])
        if matched.empty:
            raise ObjectNotFoundError(asset_id)
        row = matched.iloc[0]
        if fields is not None and "asset_id" not in fields:
            row = row.loc[fields]
        return row

    def get_row(self, *, view: DatasetView, asset_id: str) -> dict[str, object]:
        """按 asset_id 返回固定 View 的完整物理行。"""
        rows = [row for row in self.scan(view=view, columns=None) if row["asset_id"] == asset_id]
        if not rows:
            raise ObjectNotFoundError(asset_id)
        return rows[0]

    def read_image(self, *, view: DatasetView, asset_id: str) -> bytes:
        """按固定行内位置读取图片 bytes。"""
        row = self.get_row(view=view, asset_id=asset_id)
        return self._storage_manager.read_bytes(
            prefix_id=str(row["storage_prefix_id"]),
            relative_path=str(row["relative_path"]),
        )

    def verify_image(self, *, view: DatasetView, asset_id: str) -> bool:
        """验证固定行内位置的图片内容身份。"""
        row = self.get_row(view=view, asset_id=asset_id)
        return self._storage_manager.verify(
            StoredObject(
                asset_id=str(row["asset_id"]),
                storage_prefix_id=str(row["storage_prefix_id"]),
                relative_path=str(row["relative_path"]),
            )
        )

    def _dataset(self, *, view: DatasetView) -> DatasetRecord:
        return self._repositories.get_dataset(repo_id=view.repo_id, dataset_id=view.dataset_id)
