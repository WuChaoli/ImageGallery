"""仅供 DatasetManager E2E 使用的最小导入帮助类。"""

from dataclasses import dataclass

from image_gallery.dataset_manager import Dataset, DatasetView
from image_gallery.importers import SourceParser
from image_gallery.storage_manager import StorageManager


@dataclass(frozen=True, slots=True)
class DatasetManagerTestImportResult:
    """描述一次测试导入提交的可见结果。"""

    view: DatasetView
    imported_count: int
    asset_ids: tuple[str, ...]


class DatasetManagerTestImporter:
    """把 SourceParser 的本地来源导入 DatasetManager 测试 Dataset。"""

    def __init__(
        self,
        *,
        source: SourceParser,
        dataset: Dataset,
        base: DatasetView,
        storage_manager: StorageManager,
        prefix_id: str,
        tag_ids: list[str] | None = None,
    ) -> None:
        self._source = source
        self._dataset = dataset
        self._base = base
        self._storage_manager = storage_manager
        self._prefix_id = prefix_id
        self._tag_ids = sorted(set(tag_ids or []))

    def run(self) -> DatasetManagerTestImportResult:
        """读取全部本地来源，并以一次原子 commit 发布 Dataset 行。"""
        if self._base.ref_type != "branch":
            raise ValueError("base must be a Branch DatasetView")

        # 在写入托管对象前先拒绝已知 stale 基线，减少失败测试产生的孤立对象。
        current = self._dataset.open_branch(name=self._base.ref_name)
        if current.snapshot_id != self._base.snapshot_id:
            from image_gallery.dataset_manager import ConflictError

            raise ConflictError(f"Branch {self._base.ref_name} changed after the provided DatasetView")

        rows: list[dict[str, object]] = []
        asset_ids: list[str] = []
        for record in self._source.parse():
            if record.local_path is None:
                raise ValueError("local_path is required by DatasetManagerTestImporter")
            stored = self._storage_manager.write_managed(
                prefix_id=self._prefix_id,
                data=record.local_path.read_bytes(),
            )
            asset_ids.append(stored.asset_id)
            rows.append(
                {
                    "asset_id": stored.asset_id,
                    "storage_prefix_id": stored.storage_prefix_id,
                    "relative_path": stored.relative_path,
                    "source_uri": record.source_uri,
                    "tag_ids": self._tag_ids,
                }
            )

        result = self._dataset.commit(
            branch=self._base.ref_name,
            base=self._base,
            rows=rows,
        )
        return DatasetManagerTestImportResult(
            view=result.view,
            imported_count=len(rows),
            asset_ids=tuple(asset_ids),
        )
