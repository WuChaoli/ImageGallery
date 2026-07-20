"""DatasetManager 的 Dataset 历史、候选发布与恢复协作者。"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, cast

import pandas as pd
import pyarrow as pa
from pyiceberg.catalog import Catalog
from pyiceberg.exceptions import CommitFailedException
from pyiceberg.schema import Schema
from pyiceberg.table import Table
from pyiceberg.table.refs import SnapshotRefType
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine

from image_gallery.dataset_manager._operation_journal import OperationJournal
from image_gallery.dataset_manager._repository_store import DatasetRecord, RepositoryStore
from image_gallery.dataset_manager.control import asset_vectors, datasets, operations, pending_asset_vectors
from image_gallery.dataset_manager.errors import (
    ConflictError,
    NameConflictError,
    ObjectNotFoundError,
    ValidationError,
)
from image_gallery.dataset_manager.models import CommitResult, Dataset, DatasetRepo, DatasetView
from image_gallery.storage_manager import StorageManager, StoredObject

if TYPE_CHECKING:
    from image_gallery.dataset_manager.manager import DatasetManager


class DatasetHistory:
    """集中实现 Dataset 历史协议及其 durable recovery。"""

    def __init__(
        self,
        *,
        manager: DatasetManager,
        engine: Engine,  # pyright: ignore[reportUnknownParameterType]
        catalog: Catalog,  # pyright: ignore[reportUnknownParameterType]
        storage_manager: StorageManager,
        operations: OperationJournal,
        repositories: RepositoryStore,
        system_schema: Schema,
        system_fields: set[str],
    ) -> None:
        self._manager = manager
        self._engine = engine
        self.catalog = catalog
        self.storage_manager = storage_manager
        self._operations = operations
        self._repositories = repositories
        self._system_schema = system_schema
        self._system_fields = system_fields

    def recover_operations(self) -> int:
        """幂等恢复全部未完成的 Dataset 历史操作。"""
        recovered = 0
        for operation in self._operations.pending():
            if operation.kind == "create_dataset":
                self._recover_create_dataset(operation_id=operation.operation_id, intent=operation.intent)
                recovered += 1
            elif operation.kind == "commit":
                self._recover_commit(operation_id=operation.operation_id, intent=operation.intent)
                recovered += 1
            elif operation.kind == "clone":
                self._recover_clone(operation_id=operation.operation_id, intent=operation.intent)
                recovered += 1
            elif operation.kind == "checkpoint":
                self._recover_checkpoint(operation_id=operation.operation_id, intent=operation.intent)
                recovered += 1
            elif operation.kind == "rollback":
                self._recover_rollback(operation_id=operation.operation_id, intent=operation.intent)
                recovered += 1
            elif operation.kind == "branch":
                self._recover_branch(operation_id=operation.operation_id, intent=operation.intent)
                recovered += 1
        return recovered

    def _recover_create_dataset(self, *, operation_id: str, intent: dict[str, object]) -> None:
        table_identifier = str(intent["table_identifier"])
        if not self.catalog.table_exists(table_identifier):
            self.catalog.create_table(table_identifier, schema=self._system_schema)
        self._register_dataset_from_intent(operation_id=operation_id, intent=intent)

    def _recover_clone(self, *, operation_id: str, intent: dict[str, object]) -> None:
        table_identifier = str(intent["table_identifier"])
        source_table = self.catalog.load_table(str(intent["source_table_identifier"]))
        if not self.catalog.table_exists(table_identifier):
            self.catalog.create_table(table_identifier, schema=self._system_schema)
        target_table = self.catalog.load_table(table_identifier)
        self._copy_business_schema(source_table=source_table, target_table=target_table)
        target_table = self.catalog.load_table(table_identifier)
        if target_table.current_snapshot() is None:
            rows = (
                source_table.scan(snapshot_id=self._required_int(intent["source_snapshot_id"])).to_arrow().to_pylist()
            )
            target_table.append(pa.Table.from_pylist(rows, schema=target_table.schema().as_arrow()), branch="main")
            target_table = self.catalog.load_table(table_identifier)
        current = target_table.current_snapshot()
        if current is not None:
            self._verify_snapshot_storage(table=target_table, snapshot_id=current.snapshot_id)
        self._register_dataset_from_intent(operation_id=operation_id, intent=intent)

    def _recover_checkpoint(self, *, operation_id: str, intent: dict[str, object]) -> None:
        table = self.catalog.load_table(str(intent["table_identifier"]))
        name = str(intent["checkpoint"])
        snapshot_id = self._required_int(intent["snapshot_id"])
        ref = table.refs().get(name)
        if ref is None:
            table.manage_snapshots().create_tag(snapshot_id, name).commit()
        elif ref.snapshot_ref_type != SnapshotRefType.TAG or ref.snapshot_id != snapshot_id:
            raise ConflictError(name)
        self._operations.finalize(operation_id=operation_id)

    def _recover_rollback(self, *, operation_id: str, intent: dict[str, object]) -> None:
        table = self.catalog.load_table(str(intent["table_identifier"]))
        branch = str(intent["branch"])
        base = self._required_int(intent["base_snapshot_id"])
        target = self._required_int(intent["target_snapshot_id"])
        actual = self.branch_snapshot_id(table=table, branch=branch)
        if actual == base:
            snapshots = table.manage_snapshots()
            if branch == "main":
                snapshots.set_current_snapshot(snapshot_id=target).commit()
            else:
                snapshots.create_branch(target, branch).commit()
        elif actual != target:
            raise ConflictError(branch)
        self._operations.finalize(operation_id=operation_id)

    def _recover_branch(self, *, operation_id: str, intent: dict[str, object]) -> None:
        """幂等完成固定 Snapshot 的 Branch ref 创建。"""
        table = self.catalog.load_table(str(intent["table_identifier"]))
        name = str(intent["branch"])
        snapshot_id = self._required_int(intent["snapshot_id"])
        if table.snapshot_by_id(snapshot_id) is None:
            self._operations.fail(operation_id=operation_id)
            raise ConflictError(f"Source Snapshot no longer exists: {snapshot_id}")
        ref = table.refs().get(name)
        if ref is None:
            table.manage_snapshots().create_branch(snapshot_id, name).commit()
        elif ref.snapshot_ref_type != SnapshotRefType.BRANCH or ref.snapshot_id != snapshot_id:
            self._operations.fail(operation_id=operation_id)
            raise ConflictError(name)
        self._operations.finalize(operation_id=operation_id)

    def _register_dataset_from_intent(self, *, operation_id: str, intent: dict[str, object]) -> None:
        self._repositories.register_dataset(
            operation_id=operation_id,
            record=DatasetRecord(
                dataset_id=str(intent["dataset_id"]),
                repo_id=str(intent["repo_id"]),
                name=str(intent["name"]),
                table_identifier=str(intent["table_identifier"]),
            ),
            name_key=str(intent["name_key"]),
            only_if_missing=True,
        )

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise ValidationError("Operation intent requires an integer value")
        return value

    def _recover_commit(self, *, operation_id: str, intent: dict[str, object]) -> None:
        table = self.catalog.load_table(str(intent["table_identifier"]))
        branch = str(intent["branch"])
        candidate = intent.get("candidate_snapshot_id")
        actual = self.branch_snapshot_id(table=table, branch=branch)
        if candidate is None:
            base = intent.get("base_snapshot_id")
            if actual != base:
                candidate = actual
            elif bool(intent.get("data_changed")):
                rows = cast(list[dict[str, object]], intent["rows"])
                arrow_table = pa.Table.from_pylist(rows, schema=table.schema().as_arrow())
                if isinstance(base, int):
                    temporary_ref = f"op_{operation_id}"
                    table.manage_snapshots().create_branch(base, temporary_ref).commit()
                    table = self.catalog.load_table(str(intent["table_identifier"]))
                    table.overwrite(arrow_table, branch=temporary_ref)
                    table = self.catalog.load_table(str(intent["table_identifier"]))
                    candidate = self.branch_snapshot_id(table=table, branch=temporary_ref)
                    if candidate is None:
                        raise ConflictError("Temporary ref has no candidate Snapshot")
                    intent["temporary_ref"] = temporary_ref
                    self._publish_candidate(
                        table_identifier=str(intent["table_identifier"]),
                        branch=branch,
                        base_snapshot_id=base,
                        candidate_snapshot_id=candidate,
                        temporary_ref=temporary_ref,
                    )
                else:
                    table.append(arrow_table, branch=branch)
                    table = self.catalog.load_table(str(intent["table_identifier"]))
                    candidate = self.branch_snapshot_id(table=table, branch=branch)
            else:
                candidate = base
            self._operations.update_intent(
                operation_id=operation_id,
                values={
                    "candidate_snapshot_id": candidate,
                    "temporary_ref": intent.get("temporary_ref"),
                },
            )
            actual = self.branch_snapshot_id(
                table=self.catalog.load_table(str(intent["table_identifier"])),
                branch=branch,
            )
        temporary_ref = intent.get("temporary_ref")
        if actual != candidate:
            base = intent.get("base_snapshot_id")
            if not isinstance(base, int) or not isinstance(candidate, int) or not isinstance(temporary_ref, str):
                self._fail_operation(operation_id=operation_id, temporary_ref=temporary_ref, table=table)
                return
            actual = self.branch_snapshot_id(
                table=self.catalog.load_table(str(intent["table_identifier"])),
                branch=branch,
            )
            if actual not in {base, candidate}:
                self._fail_operation(operation_id=operation_id, temporary_ref=temporary_ref, table=table)
                return
            self._publish_candidate(
                table_identifier=str(intent["table_identifier"]),
                branch=branch,
                base_snapshot_id=base,
                candidate_snapshot_id=candidate,
                temporary_ref=temporary_ref,
            )
        elif isinstance(temporary_ref, str) and temporary_ref in table.refs():
            table.manage_snapshots().remove_branch(temporary_ref).commit()
        if isinstance(candidate, int):
            self._verify_snapshot_storage(table=table, snapshot_id=candidate)
        self._publish_pending_vectors_and_finalize(operation_id=operation_id)

    def _fail_operation(
        self,
        *,
        operation_id: str,
        temporary_ref: object,
        table: Table,
    ) -> None:  # pyright: ignore[reportUnknownParameterType]
        if isinstance(temporary_ref, str) and temporary_ref in table.refs():
            table.manage_snapshots().remove_branch(temporary_ref).commit()
        with self._engine.begin() as connection:
            connection.execute(
                pending_asset_vectors.delete().where(pending_asset_vectors.c.operation_id == operation_id)
            )
            connection.execute(
                update(operations).where(operations.c.operation_id == operation_id).values(status="failed")
            )

    def _verify_snapshot_storage(
        self,
        *,
        table: Table,  # pyright: ignore[reportUnknownParameterType]
        snapshot_id: int,
    ) -> None:
        rows = (
            table.scan(
                snapshot_id=snapshot_id,
                selected_fields=("asset_id", "storage_prefix_id", "relative_path"),
            )
            .to_arrow()
            .to_pylist()
        )
        for row in rows:
            self.storage_manager.verify(
                StoredObject(
                    asset_id=str(row["asset_id"]),
                    storage_prefix_id=str(row["storage_prefix_id"]),
                    relative_path=str(row["relative_path"]),
                )
            )

    def assert_dataset_visible(self, *, dataset_id: str) -> None:
        """拒绝读取仍在恢复中的 Dataset。"""
        if self._operations.has_active_dataset_operation(dataset_id=dataset_id):
            raise ConflictError(f"Dataset {dataset_id} is reconciling")

    def clone_dataset(self, *, repo: DatasetRepo, source: DatasetView, name: str) -> Dataset:
        """从固定 View 克隆独立 Dataset 状态。"""
        if source.repo_id != repo.repo_id or source._manager is not self._manager:
            raise ValidationError("Clone source must belong to the target DatasetRepo")
        if source.snapshot_id is None:
            raise ValidationError("Clone source must reference a concrete Snapshot")
        with self._engine.connect() as connection:
            if (
                connection.execute(
                    select(datasets.c.dataset_id).where(
                        datasets.c.repo_id == repo.repo_id,
                        datasets.c.name_key == name.casefold(),
                    )
                ).first()
                is not None
            ):
                raise NameConflictError(name)
        dataset_id = uuid.uuid4().hex
        table_identifier = f"{repo.namespace}.d_{dataset_id[:12]}"
        source_dataset = self._manager._dataset_by_id(repo_id=source.repo_id, dataset_id=source.dataset_id)
        source_table = self.catalog.load_table(source_dataset.table_identifier)
        rows = self._manager._scan_view(view=source, columns=None)
        operation_id = self._operations.start(
            kind="clone",
            repo_id=repo.repo_id,
            dataset_id=dataset_id,
            intent={
                "dataset_id": dataset_id,
                "repo_id": repo.repo_id,
                "name": name,
                "name_key": name.casefold(),
                "table_identifier": table_identifier,
                "source_table_identifier": source_dataset.table_identifier,
                "source_snapshot_id": source.snapshot_id,
            },
        )
        self.catalog.create_table(table_identifier, schema=self._system_schema)
        cloned_table = self.catalog.load_table(table_identifier)
        self._copy_business_schema(source_table=source_table, target_table=cloned_table)
        cloned_table = self.catalog.load_table(table_identifier)
        cloned_table.append(pa.Table.from_pylist(rows, schema=cloned_table.schema().as_arrow()), branch="main")
        self._operations.record_phase(operation_id=operation_id, phase="clone_candidate_written")
        self._register_dataset_from_intent(
            operation_id=operation_id,
            intent={
                "dataset_id": dataset_id,
                "repo_id": repo.repo_id,
                "name": name,
                "name_key": name.casefold(),
                "table_identifier": table_identifier,
            },
        )
        return Dataset(repo.repo_id, dataset_id, name, table_identifier, self._manager)

    def _copy_business_schema(
        self,
        *,
        source_table: Table,  # pyright: ignore[reportUnknownParameterType]
        target_table: Table,  # pyright: ignore[reportUnknownParameterType]
    ) -> None:
        target_names = {field.name for field in target_table.schema().fields}
        business_fields = [
            field
            for field in source_table.schema().fields
            if field.name not in self._system_fields and field.name not in target_names
        ]
        if not business_fields:
            return
        update_schema = target_table.update_schema()
        for field in business_fields:
            update_schema.add_column(field.name, field.field_type, doc=field.doc, required=False)
        update_schema.commit()

    def open_branch(self, *, dataset: Dataset, name: str) -> DatasetView:
        """打开 Dataset Branch 的固定 View。"""
        self.assert_dataset_visible(dataset_id=dataset.dataset_id)
        table = self.catalog.load_table(dataset.table_identifier)
        refs = table.refs()
        if name == "main" and name not in refs:
            current = table.current_snapshot()
            snapshot_id = current.snapshot_id if current is not None else None
        else:
            ref = refs.get(name)
            if ref is None or ref.snapshot_ref_type != SnapshotRefType.BRANCH:
                raise ObjectNotFoundError(name)
            snapshot_id = ref.snapshot_id
        return DatasetView(dataset.repo_id, dataset.dataset_id, snapshot_id, name, "branch", self._manager)

    def open_checkpoint(self, *, dataset: Dataset, name: str) -> DatasetView:
        """打开 Dataset Checkpoint 的固定 View。"""
        self.assert_dataset_visible(dataset_id=dataset.dataset_id)
        table = self.catalog.load_table(dataset.table_identifier)
        ref = table.refs().get(name)
        if ref is None or ref.snapshot_ref_type != SnapshotRefType.TAG:
            raise ObjectNotFoundError(name)
        return DatasetView(dataset.repo_id, dataset.dataset_id, ref.snapshot_id, name, "checkpoint", self._manager)

    def list_checkpoints(self, *, dataset: Dataset) -> list[str]:
        """列出 Dataset 的全部 Checkpoint 名称。"""
        self.assert_dataset_visible(dataset_id=dataset.dataset_id)
        table = self.catalog.load_table(dataset.table_identifier)
        return sorted(name for name, ref in table.refs().items() if ref.snapshot_ref_type == SnapshotRefType.TAG)

    def create_checkpoint(self, *, dataset: Dataset, name: str, source: DatasetView) -> DatasetView:
        """从固定 View 创建 Checkpoint。"""
        self._manager._validate_view_dataset(view=source, dataset=dataset)
        if source.snapshot_id is None:
            raise ValidationError("Cannot checkpoint an empty Dataset")
        table = self.catalog.load_table(dataset.table_identifier)
        if (
            source.ref_type == "branch"
            and self.branch_snapshot_id(table=table, branch=source.ref_name) != source.snapshot_id
        ):
            raise ConflictError(source.ref_name)
        operation_id = self._operations.start(
            kind="checkpoint",
            repo_id=dataset.repo_id,
            dataset_id=dataset.dataset_id,
            intent={
                "table_identifier": dataset.table_identifier,
                "checkpoint": name,
                "snapshot_id": source.snapshot_id,
            },
        )
        table.manage_snapshots().create_tag(source.snapshot_id, name).commit()
        self._operations.record_phase(operation_id=operation_id, phase="checkpoint_created")
        self._operations.finalize(operation_id=operation_id)
        return DatasetView(
            dataset.repo_id,
            dataset.dataset_id,
            source.snapshot_id,
            name,
            "checkpoint",
            self._manager,
        )

    def create_branch(self, *, dataset: Dataset, name: str, source: DatasetView) -> DatasetView:
        """从同 Dataset 的固定 View 创建 Branch。"""
        self._manager._validate_view_dataset(view=source, dataset=dataset)
        self.assert_dataset_visible(dataset_id=dataset.dataset_id)
        if source.ref_type not in {"branch", "checkpoint"} or source.snapshot_id is None:
            raise ValidationError("Branch source must be a fixed Branch or Checkpoint View")
        table = self.catalog.load_table(dataset.table_identifier)
        if table.snapshot_by_id(source.snapshot_id) is None:
            raise ValidationError(f"Source Snapshot does not exist: {source.snapshot_id}")
        source_ref = table.refs().get(source.ref_name)
        expected_ref_type = SnapshotRefType.BRANCH if source.ref_type == "branch" else SnapshotRefType.TAG
        if source_ref is None or source_ref.snapshot_ref_type != expected_ref_type:
            raise ValidationError("Branch source ref is not valid for this Dataset")
        if source.ref_type == "checkpoint" and source_ref.snapshot_id != source.snapshot_id:
            raise ValidationError("Checkpoint source no longer references the fixed Snapshot")
        if name in table.refs():
            raise NameConflictError(name)
        operation_id = self._operations.start(
            kind="branch",
            repo_id=dataset.repo_id,
            dataset_id=dataset.dataset_id,
            intent={
                "table_identifier": dataset.table_identifier,
                "branch": name,
                "snapshot_id": source.snapshot_id,
            },
        )
        try:
            table.manage_snapshots().create_branch(source.snapshot_id, name).commit()
        except (CommitFailedException, ValueError):
            self._operations.fail(operation_id=operation_id)
            raise
        self._operations.record_phase(operation_id=operation_id, phase="branch_created")
        self._operations.finalize(operation_id=operation_id)
        return self.open_branch(dataset=dataset, name=name)

    def rollback(
        self,
        *,
        dataset: Dataset,
        branch: str,
        base: DatasetView,
        checkpoint: DatasetView,
    ) -> DatasetView:
        """将 Branch 回退到同 lineage 的祖先 Checkpoint。"""
        self._manager._validate_view_dataset(view=base, dataset=dataset)
        self._manager._validate_view_dataset(view=checkpoint, dataset=dataset)
        if base.ref_type != "branch" or base.ref_name != branch or checkpoint.ref_type != "checkpoint":
            raise ValidationError("Rollback requires target Branch View and Checkpoint View")
        if base.snapshot_id is None or checkpoint.snapshot_id is None:
            raise ValidationError("Rollback requires concrete Snapshots")
        table = self.catalog.load_table(dataset.table_identifier)
        if self.branch_snapshot_id(table=table, branch=branch) != base.snapshot_id:
            raise ConflictError(branch)
        if not self._is_ancestor(table=table, ancestor=checkpoint.snapshot_id, descendant=base.snapshot_id):
            raise ValidationError("Checkpoint is not an ancestor of the target Branch")
        operation_id = self._operations.start(
            kind="rollback",
            repo_id=dataset.repo_id,
            dataset_id=dataset.dataset_id,
            intent={
                "table_identifier": dataset.table_identifier,
                "branch": branch,
                "base_snapshot_id": base.snapshot_id,
                "target_snapshot_id": checkpoint.snapshot_id,
            },
        )
        snapshots = table.manage_snapshots()
        if branch == "main":
            snapshots.set_current_snapshot(snapshot_id=checkpoint.snapshot_id).commit()
        else:
            snapshots.create_branch(checkpoint.snapshot_id, branch).commit()
        self._operations.record_phase(operation_id=operation_id, phase="rollback_published")
        self._operations.finalize(operation_id=operation_id)
        return DatasetView(
            dataset.repo_id,
            dataset.dataset_id,
            checkpoint.snapshot_id,
            branch,
            "branch",
            self._manager,
        )

    @staticmethod
    def _is_ancestor(  # pyright: ignore[reportUnknownParameterType]
        *,
        table: Table,
        ancestor: int,
        descendant: int,
    ) -> bool:
        current_id: int | None = descendant
        while current_id is not None:
            if current_id == ancestor:
                return True
            snapshot = table.snapshot_by_id(current_id)
            if snapshot is None:
                return False
            current_id = snapshot.parent_snapshot_id
        return False

    def commit(
        self,
        *,
        dataset: Dataset,
        branch: str,
        base: DatasetView,
        frame: pd.DataFrame,
        fields: list[str] | None,
    ) -> CommitResult:
        """规范化 DataFrame 并提交到目标 Branch。"""
        vector_names = {
            item.name for item in self._manager._list_vector_fields(repo=self._manager._repo_by_id(dataset.repo_id))
        }
        requested = set(fields or []) | {str(column) for column in frame.columns}
        if requested & vector_names:
            raise ValidationError("Vector fields cannot be committed directly; use dataset.generate_embed()")
        records = cast(list[dict[str, object]], frame.to_dict(orient="records"))
        if fields is not None:
            if "asset_id" not in frame.columns or "asset_id" in fields:
                raise ValidationError("Patch commit requires asset_id outside fields")
            current = {str(row["asset_id"]): row for row in self._manager._scan_view(view=base, columns=None)}
            rows: list[dict[str, object]] = []
            for patch in records:
                asset_id = str(patch["asset_id"])
                if asset_id not in current:
                    raise ValidationError("Patch commit only supports existing asset_id")
                if not set(fields).issubset(patch):
                    raise ValidationError("Patch frame must contain every requested field")
                rows.append({**current[asset_id], **{name: patch[name] for name in fields}})
        else:
            rows = records
        return self.commit_rows(dataset=dataset, branch=branch, base=base, rows=rows)

    def commit_rows(
        self,
        *,
        dataset: Dataset,
        branch: str,
        base: DatasetView,
        rows: list[dict[str, object]],
    ) -> CommitResult:
        """以规范化行集合推进目标 Branch。"""
        self._manager._validate_view_dataset(view=base, dataset=dataset)
        if base.ref_type != "branch" or base.ref_name != branch:
            raise ValidationError("Commit base must be the target Branch View")
        self.assert_dataset_visible(dataset_id=dataset.dataset_id)
        table = self.catalog.load_table(dataset.table_identifier)
        if self.branch_snapshot_id(table=table, branch=branch) != base.snapshot_id:
            raise ConflictError(branch)
        allowed_fields = {field.name for field in table.schema().fields}
        normalized_rows = [
            self._manager._normalize_row(repo_id=dataset.repo_id, row=row, allowed_fields=allowed_fields)
            for row in rows
        ]
        asset_ids = [str(row["asset_id"]) for row in normalized_rows]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValidationError("Duplicate asset_id in one change set")
        current_rows = self._manager._scan_view(view=base, columns=None)
        by_id = {str(row["asset_id"]): row for row in current_rows}
        inserted = sum(asset_id not in by_id for asset_id in asset_ids)
        updated = len(asset_ids) - inserted
        for row in normalized_rows:
            by_id[str(row["asset_id"])] = row
        merged_rows = sorted(by_id.values(), key=lambda item: str(item["asset_id"]))
        pending_vectors: list[dict[str, object]] = []
        data_changed = merged_rows != sorted(current_rows, key=lambda item: str(item["asset_id"]))
        if not data_changed and not pending_vectors:
            return CommitResult(base, inserted=0, updated=0, changed=False)
        operation_id = self._operations.start(
            kind="commit",
            repo_id=dataset.repo_id,
            dataset_id=dataset.dataset_id,
            intent={
                "repo_id": dataset.repo_id,
                "dataset_id": dataset.dataset_id,
                "table_identifier": dataset.table_identifier,
                "branch": branch,
                "base_snapshot_id": base.snapshot_id,
                "candidate_snapshot_id": None,
                "temporary_ref": None,
                "rows": merged_rows,
                "data_changed": data_changed,
            },
        )
        self._insert_pending_vectors(operation_id=operation_id, pending=pending_vectors)
        self._operations.record_phase(operation_id=operation_id, phase="pending_vectors_written")
        candidate_snapshot_id = base.snapshot_id
        if data_changed:
            arrow_table = pa.Table.from_pylist(merged_rows, schema=table.schema().as_arrow())
            if base.snapshot_id is None:
                table.append(arrow_table, branch=branch)
                table = self.catalog.load_table(dataset.table_identifier)
                candidate_snapshot_id = self.branch_snapshot_id(table=table, branch=branch)
            else:
                temporary_ref = f"op_{operation_id}"
                table.manage_snapshots().create_branch(base.snapshot_id, temporary_ref).commit()
                table = self.catalog.load_table(dataset.table_identifier)
                table.overwrite(arrow_table, branch=temporary_ref)
                table = self.catalog.load_table(dataset.table_identifier)
                candidate_snapshot_id = self.branch_snapshot_id(table=table, branch=temporary_ref)
                if candidate_snapshot_id is None:
                    raise ConflictError("Temporary ref has no candidate Snapshot")
                self._operations.update_intent(
                    operation_id=operation_id,
                    values={
                        "candidate_snapshot_id": candidate_snapshot_id,
                        "temporary_ref": temporary_ref,
                    },
                )
                self._operations.record_phase(
                    operation_id=operation_id,
                    phase="candidate_written",
                    details={"snapshot_id": candidate_snapshot_id},
                )
                self._publish_candidate(
                    table_identifier=dataset.table_identifier,
                    branch=branch,
                    base_snapshot_id=base.snapshot_id,
                    candidate_snapshot_id=candidate_snapshot_id,
                    temporary_ref=temporary_ref,
                )
        self._operations.update_intent(
            operation_id=operation_id,
            values={"candidate_snapshot_id": candidate_snapshot_id},
        )
        if base.snapshot_id is None or not data_changed:
            self._operations.record_phase(
                operation_id=operation_id,
                phase="candidate_written",
                details={"snapshot_id": candidate_snapshot_id},
            )
        self._publish_pending_vectors_and_finalize(operation_id=operation_id)
        self._operations.record_phase(operation_id=operation_id, phase="vectors_published")
        view = DatasetView(
            dataset.repo_id,
            dataset.dataset_id,
            candidate_snapshot_id,
            branch,
            "branch",
            self._manager,
        )
        return CommitResult(view, inserted=inserted, updated=updated, changed=data_changed)

    def _insert_pending_vectors(self, *, operation_id: str, pending: list[dict[str, object]]) -> None:
        if not pending:
            return
        with self._engine.begin() as connection:
            connection.execute(
                insert(pending_asset_vectors),
                [{"operation_id": operation_id, **item} for item in pending],
            )

    def _publish_pending_vectors_and_finalize(self, *, operation_id: str) -> None:
        with self._engine.begin() as connection:
            rows = (
                connection.execute(
                    select(pending_asset_vectors).where(pending_asset_vectors.c.operation_id == operation_id)
                )
                .mappings()
                .all()
            )
            for row in rows:
                key = (
                    asset_vectors.c.repo_id == row["repo_id"],
                    asset_vectors.c.vector_field_id == row["vector_field_id"],
                    asset_vectors.c.asset_id == row["asset_id"],
                )
                existing = connection.execute(select(asset_vectors.c.asset_id).where(*key)).first()
                if existing is None:
                    connection.execute(
                        insert(asset_vectors).values(
                            repo_id=row["repo_id"],
                            vector_field_id=row["vector_field_id"],
                            asset_id=row["asset_id"],
                            value=row["value"],
                        )
                    )
                else:
                    connection.execute(update(asset_vectors).where(*key).values(value=row["value"]))
            connection.execute(
                pending_asset_vectors.delete().where(pending_asset_vectors.c.operation_id == operation_id)
            )
            connection.execute(
                update(operations).where(operations.c.operation_id == operation_id).values(status="finalized")
            )

    def _publish_candidate(
        self,
        *,
        table_identifier: str,
        branch: str,
        base_snapshot_id: int,
        candidate_snapshot_id: int,
        temporary_ref: str,
    ) -> None:
        table = self.catalog.load_table(table_identifier)
        actual = self.branch_snapshot_id(table=table, branch=branch)
        if actual == candidate_snapshot_id:
            if temporary_ref in table.refs():
                table.manage_snapshots().remove_branch(temporary_ref).commit()
            return
        if actual != base_snapshot_id:
            raise ConflictError(branch)
        table.manage_snapshots().create_branch(candidate_snapshot_id, branch).remove_branch(temporary_ref).commit()

    @staticmethod
    def branch_snapshot_id(
        *,
        table: Table,  # pyright: ignore[reportUnknownParameterType]
        branch: str,
    ) -> int | None:
        """返回 Branch 当前 Snapshot ID。"""
        refs = table.refs()
        if branch == "main" and branch not in refs:
            current = table.current_snapshot()
            return current.snapshot_id if current is not None else None
        ref = refs.get(branch)
        if ref is None or ref.snapshot_ref_type != SnapshotRefType.BRANCH:
            raise ObjectNotFoundError(branch)
        return ref.snapshot_id
