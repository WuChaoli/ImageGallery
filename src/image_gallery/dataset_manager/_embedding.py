"""Dataset 范围向量生成的私有服务。"""

from __future__ import annotations

from image_gallery.dataset_manager._vector_store import VectorStore
from image_gallery.dataset_manager._view_io import ViewIO
from image_gallery.dataset_manager.models import Dataset, DatasetView, EmbedResult, VectorField
from image_gallery.model_manager import ModelManager
from image_gallery.storage_manager import StorageManager, StoredObject

_EMBED_BATCH_SIZE = 64


class EmbeddingService:
    """对已固定合法 View 执行可信批量推理和原子发布。"""

    def __init__(
        self,
        *,
        storage_manager: StorageManager,
        model_manager: ModelManager,
        vectors: VectorStore,
        view_io: ViewIO,
    ) -> None:
        """绑定生成流程所需的后端依赖。"""
        self._storage_manager = storage_manager
        self._model_manager = model_manager
        self._vectors = vectors
        self._view_io = view_io

    def generate(
        self,
        *,
        dataset: Dataset,
        field: VectorField,
        view: DatasetView,
        overwrite: bool,
    ) -> EmbedResult:
        """为固定 View 生成缺失或全部 Repo 当前向量。"""
        rows = self._view_io.scan(view=view, columns=["asset_id", "storage_prefix_id", "relative_path"])
        asset_ids = [str(row["asset_id"]) for row in rows]
        existing = self._vectors.list_existing(
            repo_id=dataset.repo_id,
            vector_field_id=field.vector_field_id,
            asset_ids=asset_ids,
        )
        targets = rows if overwrite else [row for row in rows if str(row["asset_id"]) not in existing]
        images: list[bytes] = []
        for row in targets:
            stored = StoredObject(str(row["asset_id"]), str(row["storage_prefix_id"]), str(row["relative_path"]))
            self._storage_manager.verify(stored)
            images.append(
                self._storage_manager.read_bytes(
                    prefix_id=stored.storage_prefix_id,
                    relative_path=stored.relative_path,
                )
            )
        outputs: list[tuple[float, ...]] = []
        for offset in range(0, len(images), _EMBED_BATCH_SIZE):
            outputs.extend(
                self._model_manager.embed(
                    model_id=field.model_id,
                    images=images[offset : offset + _EMBED_BATCH_SIZE],
                )
            )
        values = {str(row["asset_id"]): value for row, value in zip(targets, outputs, strict=True)}
        generated, updated = self._vectors.publish_current(
            repo_id=dataset.repo_id,
            vector_field_id=field.vector_field_id,
            values=values,
            existing=existing,
        )
        return EmbedResult(view.snapshot_id, generated, updated, len(rows) - len(targets))
