"""DatasetManager Backend 生命周期入口。"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pyarrow as pa
from pyiceberg.catalog import Catalog, load_catalog
from pyiceberg.schema import Schema
from pyiceberg.table import Table
from pyiceberg.table.refs import SnapshotRefType
from pyiceberg.types import BooleanType, DoubleType, IntegerType, ListType, LongType, NestedField, StringType
from sqlalchemy import create_engine, insert, select, update
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.exc import IntegrityError

from image_gallery.dataset_manager.control import (
    asset_vectors,
    datasets,
    metadata,
    operation_phases,
    operations,
    pending_asset_vectors,
    repo_storage_bindings,
    repos,
    tag_definitions,
    vector_fields,
    vector_validation_items,
)
from image_gallery.dataset_manager.errors import (
    ConflictError,
    NameConflictError,
    ObjectNotFoundError,
    StorageAuthorizationError,
    ValidationError,
)
from image_gallery.dataset_manager.migrations import upgrade_control_database
from image_gallery.dataset_manager.models import (
    CommitResult,
    Dataset,
    DatasetRepo,
    DatasetView,
    TagDefinition,
    VectorCommit,
    VectorField,
    VectorValidationItem,
    VectorWriteResult,
)
from image_gallery.storage_manager import PrefixNotFoundError, StorageManager, StoredObject

SYSTEM_SCHEMA = Schema(
    NestedField(1, "asset_id", StringType(), required=True),
    NestedField(2, "storage_prefix_id", StringType(), required=True),
    NestedField(3, "relative_path", StringType(), required=True),
    NestedField(4, "source_uri", StringType(), required=False),
    NestedField(5, "tag_ids", ListType(6, StringType(), element_required=False), required=True),
    identifier_field_ids=[1],
)
_ASSET_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_SYSTEM_FIELDS = {"asset_id", "storage_prefix_id", "relative_path", "source_uri", "tag_ids"}
_BUSINESS_FIELD_TYPES = {
    "boolean": BooleanType,
    "double": DoubleType,
    "integer": IntegerType,
    "long": LongType,
    "string": StringType,
}


class DatasetManager:
    """管理 DatasetRepo 的连接与生命周期。"""

    def __init__(
        self,
        *,
        control_engine: Engine,  # pyright: ignore[reportUnknownParameterType]
        catalog: Catalog,  # pyright: ignore[reportUnknownParameterType]
        storage_manager: StorageManager,
        operation_hook: Callable[[str, str], None] | None = None,
        owns_engine: bool = False,
        owns_catalog: bool = False,
    ) -> None:
        """使用显式 Backend 组合创建 DatasetManager。"""
        self._engine = control_engine
        self.catalog = catalog
        self.storage_manager = storage_manager
        self._operation_hook = operation_hook
        self._owns_engine = owns_engine
        self._owns_catalog = owns_catalog
        if self._engine.dialect.name == "postgresql":
            upgrade_control_database(self._engine)
        else:
            metadata.create_all(self._engine)

    @classmethod
    def local(
        cls,
        *,
        root: str | Path,
        storage_manager: StorageManager,
        operation_hook: Callable[[str, str], None] | None = None,
    ) -> DatasetManager:
        """创建使用 SQLite Catalog 和本地 Warehouse 的测试 Backend。"""
        root_path = Path(root).resolve()
        root_path.mkdir(parents=True, exist_ok=True)
        warehouse = root_path / "warehouse"
        warehouse.mkdir(parents=True, exist_ok=True)
        control_engine = create_engine(f"sqlite:///{(root_path / 'control.db').as_posix()}").execution_options(
            schema_translate_map={"control": None, "vectors": None}
        )
        catalog = load_catalog(
            "dataset-manager-local",
            type="sql",
            uri=f"sqlite:///{(root_path / 'catalog.db').as_posix()}",
            warehouse=warehouse.as_uri(),
            **{"py-io-impl": "image_gallery.dataset_manager.file_io.IsolatedFsspecFileIO"},
        )
        return cls(
            control_engine=control_engine,
            catalog=catalog,
            storage_manager=storage_manager,
            operation_hook=operation_hook,
            owns_engine=True,
            owns_catalog=True,
        )

    @classmethod
    def postgres(
        cls,
        *,
        control_url: str,
        catalog_url: str,
        warehouse: str,
        storage_manager: StorageManager,
        catalog_properties: dict[str, str] | None = None,
        operation_hook: Callable[[str, str], None] | None = None,
    ) -> DatasetManager:
        """创建 PostgreSQL/SqlCatalog 真实 Backend。"""
        properties = dict(catalog_properties or {})
        properties.setdefault("py-io-impl", "image_gallery.dataset_manager.file_io.IsolatedFsspecFileIO")
        control_engine = create_engine(control_url, pool_pre_ping=True)
        # PyIceberg 会在构造 SqlCatalog 时立即创建内部表，因此 schema 必须先完成迁移。
        upgrade_control_database(control_engine)
        catalog = load_catalog(
            "dataset-manager-postgres",
            type="sql",
            uri=catalog_url,
            warehouse=warehouse,
            **properties,
        )
        return cls(
            control_engine=control_engine,
            catalog=catalog,
            storage_manager=storage_manager,
            operation_hook=operation_hook,
            owns_engine=True,
            owns_catalog=True,
        )

    def close(self) -> None:
        """释放由 DatasetManager factory 创建的数据库连接池。"""
        try:
            if self._owns_engine:
                self._engine.dispose()
        finally:
            close_catalog = getattr(self.catalog, "close", None)
            if self._owns_catalog and callable(close_catalog):
                close_catalog()

    def __enter__(self) -> DatasetManager:
        """返回由上下文管理的 DatasetManager。"""
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        """退出上下文时释放内部创建的数据库连接池。"""
        self.close()

    def create_repo(self, *, name: str) -> DatasetRepo:
        """创建硬隔离 DatasetRepo 和 Iceberg Namespace。"""
        repo_id = uuid.uuid4().hex
        namespace = f"r_{repo_id[:12]}"
        self.catalog.create_namespace(namespace)
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    insert(repos).values(repo_id=repo_id, name=name, name_key=name.casefold(), namespace=namespace)
                )
        except IntegrityError as exc:
            self.catalog.drop_namespace(namespace)
            raise NameConflictError(name) from exc
        return DatasetRepo(repo_id=repo_id, name=name, namespace=namespace, _manager=self)

    def open_repo(self, *, name: str) -> DatasetRepo:
        """按大小写不敏感名称打开 DatasetRepo。"""
        statement = select(repos).where(repos.c.name_key == name.casefold())
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise ObjectNotFoundError(name)
        return self._repo_from_row(row)

    def list_repos(self) -> list[DatasetRepo]:
        """按名称返回全部 DatasetRepo。"""
        with self._engine.connect() as connection:
            rows = connection.execute(select(repos).order_by(repos.c.name_key)).mappings().all()
        return [self._repo_from_row(row) for row in rows]

    def _create_dataset(self, *, repo: DatasetRepo, name: str) -> Dataset:
        dataset_id = uuid.uuid4().hex
        table_identifier = f"{repo.namespace}.d_{dataset_id[:12]}"
        operation_id = self._start_operation(
            kind="create_dataset",
            repo_id=repo.repo_id,
            dataset_id=dataset_id,
            intent={
                "dataset_id": dataset_id,
                "repo_id": repo.repo_id,
                "name": name,
                "name_key": name.casefold(),
                "table_identifier": table_identifier,
            },
        )
        try:
            self.catalog.create_table(table_identifier, schema=SYSTEM_SCHEMA)
            self._record_phase(operation_id=operation_id, phase="table_created")
            self._emit_operation_event(operation_id=operation_id, phase="table_created")
            with self._engine.begin() as connection:
                connection.execute(
                    insert(datasets).values(
                        dataset_id=dataset_id,
                        repo_id=repo.repo_id,
                        name=name,
                        name_key=name.casefold(),
                        table_identifier=table_identifier,
                    )
                )
                connection.execute(
                    update(operations).where(operations.c.operation_id == operation_id).values(status="finalized")
                )
        except IntegrityError as exc:
            with self._engine.begin() as connection:
                connection.execute(
                    update(operations).where(operations.c.operation_id == operation_id).values(status="failed")
                )
            raise NameConflictError(name) from exc
        return Dataset(
            repo_id=repo.repo_id,
            dataset_id=dataset_id,
            name=name,
            table_identifier=table_identifier,
            _manager=self,
        )

    def recover_operations(self) -> int:
        """探测实际 Backend 状态并幂等推进全部未完成操作。"""
        statement = select(operations).where(operations.c.status == "active").order_by(operations.c.operation_id)
        with self._engine.connect() as connection:
            pending = connection.execute(statement).mappings().all()
        recovered = 0
        for row in pending:
            if row["kind"] == "create_dataset":
                self._recover_create_dataset(operation_id=str(row["operation_id"]), intent=dict(row["intent"]))
                recovered += 1
            elif row["kind"] == "commit":
                self._recover_commit(operation_id=str(row["operation_id"]), intent=dict(row["intent"]))
                recovered += 1
            elif row["kind"] == "clone":
                self._recover_clone(operation_id=str(row["operation_id"]), intent=dict(row["intent"]))
                recovered += 1
            elif row["kind"] == "checkpoint":
                self._recover_checkpoint(operation_id=str(row["operation_id"]), intent=dict(row["intent"]))
                recovered += 1
            elif row["kind"] == "rollback":
                self._recover_rollback(operation_id=str(row["operation_id"]), intent=dict(row["intent"]))
                recovered += 1
        return recovered

    def _recover_create_dataset(self, *, operation_id: str, intent: dict[str, object]) -> None:
        table_identifier = str(intent["table_identifier"])
        if not self.catalog.table_exists(table_identifier):
            self.catalog.create_table(table_identifier, schema=SYSTEM_SCHEMA)
        self._register_dataset_from_intent(operation_id=operation_id, intent=intent)

    def _recover_clone(self, *, operation_id: str, intent: dict[str, object]) -> None:
        table_identifier = str(intent["table_identifier"])
        source_table = self.catalog.load_table(str(intent["source_table_identifier"]))
        if not self.catalog.table_exists(table_identifier):
            self.catalog.create_table(table_identifier, schema=SYSTEM_SCHEMA)
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
        self._finalize_operation(operation_id=operation_id)

    def _recover_rollback(self, *, operation_id: str, intent: dict[str, object]) -> None:
        table = self.catalog.load_table(str(intent["table_identifier"]))
        branch = str(intent["branch"])
        base = self._required_int(intent["base_snapshot_id"])
        target = self._required_int(intent["target_snapshot_id"])
        actual = self._branch_snapshot_id(table=table, branch=branch)
        if actual == base:
            snapshots = table.manage_snapshots()
            if branch == "main":
                snapshots.set_current_snapshot(snapshot_id=target).commit()
            else:
                snapshots.create_branch(target, branch).commit()
        elif actual != target:
            raise ConflictError(branch)
        self._finalize_operation(operation_id=operation_id)

    def _register_dataset_from_intent(self, *, operation_id: str, intent: dict[str, object]) -> None:
        with self._engine.begin() as connection:
            existing = connection.execute(
                select(datasets.c.dataset_id).where(datasets.c.dataset_id == str(intent["dataset_id"]))
            ).first()
            if existing is None:
                connection.execute(
                    insert(datasets).values(
                        dataset_id=str(intent["dataset_id"]),
                        repo_id=str(intent["repo_id"]),
                        name=str(intent["name"]),
                        name_key=str(intent["name_key"]),
                        table_identifier=str(intent["table_identifier"]),
                    )
                )
            connection.execute(
                update(operations).where(operations.c.operation_id == operation_id).values(status="finalized")
            )

    def _start_operation(
        self,
        *,
        kind: str,
        repo_id: str,
        dataset_id: str | None,
        intent: dict[str, object],
    ) -> str:
        operation_id = uuid.uuid4().hex
        with self._engine.begin() as connection:
            connection.execute(
                insert(operations).values(
                    operation_id=operation_id,
                    repo_id=repo_id,
                    dataset_id=dataset_id,
                    kind=kind,
                    status="active",
                    intent=intent,
                )
            )
        return operation_id

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, int):
            raise ValidationError("Operation intent requires an integer value")
        return value

    def _recover_commit(self, *, operation_id: str, intent: dict[str, object]) -> None:
        table = self.catalog.load_table(str(intent["table_identifier"]))
        branch = str(intent["branch"])
        candidate = intent.get("candidate_snapshot_id")
        actual = self._branch_snapshot_id(table=table, branch=branch)
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
                    candidate = self._branch_snapshot_id(table=table, branch=temporary_ref)
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
                    candidate = self._branch_snapshot_id(table=table, branch=branch)
            else:
                candidate = base
            self._update_operation_intent(
                operation_id=operation_id,
                values={
                    "candidate_snapshot_id": candidate,
                    "temporary_ref": intent.get("temporary_ref"),
                },
            )
            actual = self._branch_snapshot_id(
                table=self.catalog.load_table(str(intent["table_identifier"])),
                branch=branch,
            )
        temporary_ref = intent.get("temporary_ref")
        if actual != candidate:
            base = intent.get("base_snapshot_id")
            if not isinstance(base, int) or not isinstance(candidate, int) or not isinstance(temporary_ref, str):
                self._fail_operation(operation_id=operation_id, temporary_ref=temporary_ref, table=table)
                return
            actual = self._branch_snapshot_id(
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

    def _verify_snapshot_storage(self, *, table: Table, snapshot_id: int) -> None:  # pyright: ignore[reportUnknownParameterType]
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

    def _assert_dataset_visible(self, *, dataset_id: str) -> None:
        statement = select(operations.c.operation_id).where(
            operations.c.dataset_id == dataset_id,
            operations.c.status == "active",
        )
        with self._engine.connect() as connection:
            if connection.execute(statement).first() is not None:
                raise ConflictError(f"Dataset {dataset_id} is reconciling")

    def _update_operation_intent(self, *, operation_id: str, values: dict[str, object]) -> None:
        with self._engine.begin() as connection:
            intent = dict(
                connection.execute(
                    select(operations.c.intent).where(operations.c.operation_id == operation_id)
                ).scalar_one()
            )
            intent.update(values)
            connection.execute(
                update(operations).where(operations.c.operation_id == operation_id).values(intent=intent)
            )

    def _finalize_operation(self, *, operation_id: str) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                update(operations).where(operations.c.operation_id == operation_id).values(status="finalized")
            )

    def _record_phase(self, *, operation_id: str, phase: str, details: dict[str, object] | None = None) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                insert(operation_phases).values(
                    operation_id=operation_id,
                    phase=phase,
                    status="complete",
                    details=details,
                )
            )

    def _emit_operation_event(self, *, operation_id: str, phase: str) -> None:
        if self._operation_hook is not None:
            self._operation_hook(operation_id, phase)

    def _open_dataset(self, *, repo: DatasetRepo, name: str) -> Dataset:
        statement = select(datasets).where(
            datasets.c.repo_id == repo.repo_id,
            datasets.c.name_key == name.casefold(),
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise ObjectNotFoundError(name)
        return self._dataset_from_row(row)

    def _list_datasets(self, *, repo: DatasetRepo) -> list[Dataset]:
        statement = select(datasets).where(datasets.c.repo_id == repo.repo_id).order_by(datasets.c.name_key)
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [self._dataset_from_row(row) for row in rows]

    def _bind_storage_prefix(self, *, repo: DatasetRepo, prefix_id: str) -> None:
        try:
            self.storage_manager.get_prefix(prefix_id=prefix_id)
        except PrefixNotFoundError:
            raise
        with self._engine.begin() as connection:
            existing = connection.execute(
                select(repo_storage_bindings).where(
                    repo_storage_bindings.c.repo_id == repo.repo_id,
                    repo_storage_bindings.c.prefix_id == prefix_id,
                )
            ).first()
            if existing is None:
                connection.execute(insert(repo_storage_bindings).values(repo_id=repo.repo_id, prefix_id=prefix_id))

    def _list_storage_prefix_ids(self, *, repo: DatasetRepo) -> list[str]:
        statement = (
            select(repo_storage_bindings.c.prefix_id)
            .where(repo_storage_bindings.c.repo_id == repo.repo_id)
            .order_by(repo_storage_bindings.c.prefix_id)
        )
        with self._engine.connect() as connection:
            return list(connection.execute(statement).scalars())

    def _create_tag(
        self,
        *,
        repo: DatasetRepo,
        name: str,
        color: str | None,
        description: str | None,
    ) -> TagDefinition:
        tag_id = uuid.uuid4().hex
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    insert(tag_definitions).values(
                        tag_id=tag_id,
                        repo_id=repo.repo_id,
                        name=name,
                        name_key=name.casefold(),
                        color=color,
                        description=description,
                        archived=False,
                    )
                )
        except IntegrityError as exc:
            raise NameConflictError(name) from exc
        return TagDefinition(tag_id, repo.repo_id, name, color, description, False)

    def _rename_tag(self, *, repo: DatasetRepo, tag_id: str, name: str) -> TagDefinition:
        statement = select(tag_definitions).where(
            tag_definitions.c.repo_id == repo.repo_id,
            tag_definitions.c.tag_id == tag_id,
        )
        try:
            with self._engine.begin() as connection:
                row = connection.execute(statement).mappings().one_or_none()
                if row is None:
                    raise ObjectNotFoundError(tag_id)
                connection.execute(
                    update(tag_definitions)
                    .where(tag_definitions.c.repo_id == repo.repo_id, tag_definitions.c.tag_id == tag_id)
                    .values(name=name, name_key=name.casefold())
                )
        except IntegrityError as exc:
            raise NameConflictError(name) from exc
        return TagDefinition(tag_id, repo.repo_id, name, row["color"], row["description"], bool(row["archived"]))

    def _archive_tag(self, *, repo: DatasetRepo, tag_id: str) -> TagDefinition:
        statement = select(tag_definitions).where(
            tag_definitions.c.repo_id == repo.repo_id,
            tag_definitions.c.tag_id == tag_id,
        )
        with self._engine.begin() as connection:
            row = connection.execute(statement).mappings().one_or_none()
            if row is None:
                raise ObjectNotFoundError(tag_id)
            connection.execute(
                update(tag_definitions)
                .where(tag_definitions.c.repo_id == repo.repo_id, tag_definitions.c.tag_id == tag_id)
                .values(archived=True)
            )
        return TagDefinition(tag_id, repo.repo_id, str(row["name"]), row["color"], row["description"], True)

    def _create_vector_field(
        self,
        *,
        repo: DatasetRepo,
        name: str,
        dimension: int,
        numeric_type: str,
        distance: str,
        validation_set: list[VectorValidationItem],
        tolerance: float,
    ) -> VectorField:
        if dimension <= 0 or tolerance < 0 or not validation_set:
            raise ValidationError("VectorField requires a positive dimension and non-empty validation set")
        if numeric_type != "float32" or distance not in {"cosine", "dot", "l2"}:
            raise ValidationError("VectorField requires numeric_type=float32 and a supported distance")
        for item in validation_set:
            self._validate_vector(value=item.expected, dimension=dimension)
        vector_field_id = uuid.uuid4().hex
        serialized = [{"probe_hex": item.probe.hex(), "expected": list(item.expected)} for item in validation_set]
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    insert(vector_fields).values(
                        vector_field_id=vector_field_id,
                        repo_id=repo.repo_id,
                        name=name,
                        name_key=name.casefold(),
                        dimension=dimension,
                        numeric_type=numeric_type,
                        distance=distance,
                        tolerance=tolerance,
                        validation_set=serialized,
                    )
                )
                connection.execute(
                    insert(vector_validation_items),
                    [
                        {
                            "vector_field_id": vector_field_id,
                            "position": position,
                            "probe": item.probe,
                            "probe_hash": f"sha256:{hashlib.sha256(item.probe).hexdigest()}",
                            "expected": list(item.expected),
                        }
                        for position, item in enumerate(validation_set)
                    ],
                )
        except IntegrityError as exc:
            raise NameConflictError(name) from exc
        return VectorField(
            vector_field_id,
            repo.repo_id,
            name,
            dimension,
            numeric_type,
            distance,
            tolerance,
            tuple(validation_set),
            self,
        )

    def _open_vector_field(self, *, repo: DatasetRepo, name: str) -> VectorField:
        statement = select(vector_fields).where(
            vector_fields.c.repo_id == repo.repo_id,
            vector_fields.c.name_key == name.casefold(),
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise ObjectNotFoundError(name)
        return self._vector_field_from_row(row)

    def _get_vector_field(self, *, repo: DatasetRepo, vector_field_id: str) -> VectorField:
        statement = select(vector_fields).where(
            vector_fields.c.repo_id == repo.repo_id,
            vector_fields.c.vector_field_id == vector_field_id,
        )
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise ObjectNotFoundError(vector_field_id)
        return self._vector_field_from_row(row)

    def _list_vector_fields(self, *, repo: DatasetRepo) -> list[VectorField]:
        statement = (
            select(vector_fields).where(vector_fields.c.repo_id == repo.repo_id).order_by(vector_fields.c.name_key)
        )
        with self._engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [self._vector_field_from_row(row) for row in rows]

    def _clone_dataset(self, *, repo: DatasetRepo, source: DatasetView, name: str) -> Dataset:
        if source.repo_id != repo.repo_id or source._manager is not self:
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
        source_dataset = self._dataset_by_id(repo_id=source.repo_id, dataset_id=source.dataset_id)
        source_table = self.catalog.load_table(source_dataset.table_identifier)
        rows = self._scan_view(view=source, columns=None)
        operation_id = self._start_operation(
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
        self.catalog.create_table(table_identifier, schema=SYSTEM_SCHEMA)
        cloned_table = self.catalog.load_table(table_identifier)
        self._copy_business_schema(source_table=source_table, target_table=cloned_table)
        cloned_table = self.catalog.load_table(table_identifier)
        cloned_table.append(pa.Table.from_pylist(rows, schema=cloned_table.schema().as_arrow()), branch="main")
        self._record_phase(operation_id=operation_id, phase="clone_candidate_written")
        self._emit_operation_event(operation_id=operation_id, phase="clone_candidate_written")
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
        return Dataset(repo.repo_id, dataset_id, name, table_identifier, self)

    @staticmethod
    def _copy_business_schema(*, source_table: Table, target_table: Table) -> None:  # pyright: ignore[reportUnknownParameterType]
        target_names = {field.name for field in target_table.schema().fields}
        business_fields = [
            field
            for field in source_table.schema().fields
            if field.name not in _SYSTEM_FIELDS and field.name not in target_names
        ]
        if not business_fields:
            return
        update_schema = target_table.update_schema()
        for field in business_fields:
            update_schema.add_column(field.name, field.field_type, doc=field.doc, required=False)
        update_schema.commit()

    def _write_vectors(
        self,
        *,
        field: VectorField,
        source: DatasetView,
        items: dict[str, tuple[float, ...]],
        validation_outputs: list[tuple[float, ...]],
        overwrite: bool,
    ) -> VectorWriteResult:
        if source.repo_id != field.repo_id or source._manager is not self:
            raise ValidationError("Source DatasetView belongs to another Repo")
        active_statement = (
            select(pending_asset_vectors.c.operation_id)
            .join(operations, operations.c.operation_id == pending_asset_vectors.c.operation_id)
            .where(
                pending_asset_vectors.c.repo_id == field.repo_id,
                pending_asset_vectors.c.vector_field_id == field.vector_field_id,
                operations.c.status == "active",
            )
        )
        with self._engine.connect() as connection:
            if connection.execute(active_statement).first() is not None:
                raise ConflictError(f"VectorField {field.vector_field_id} has an active combined commit")
        self._validate_vector_outputs(field=field, outputs=validation_outputs)
        source_ids = {str(row["asset_id"]) for row in self._scan_view(view=source, columns=["asset_id"])}
        if not set(items).issubset(source_ids):
            raise ValidationError("Every vector asset_id must be a member of the source DatasetView")
        for value in items.values():
            self._validate_vector(value=value, dimension=field.dimension)
        inserted_count = 0
        updated_count = 0
        skipped_count = 0
        with self._engine.begin() as connection:
            for asset_id, value in items.items():
                key = (
                    asset_vectors.c.repo_id == field.repo_id,
                    asset_vectors.c.vector_field_id == field.vector_field_id,
                    asset_vectors.c.asset_id == asset_id,
                )
                exists = connection.execute(select(asset_vectors.c.asset_id).where(*key)).first() is not None
                if exists and not overwrite:
                    skipped_count += 1
                elif exists:
                    connection.execute(update(asset_vectors).where(*key).values(value=list(value)))
                    updated_count += 1
                else:
                    connection.execute(
                        insert(asset_vectors).values(
                            repo_id=field.repo_id,
                            vector_field_id=field.vector_field_id,
                            asset_id=asset_id,
                            value=list(value),
                        )
                    )
                    inserted_count += 1
        return VectorWriteResult(inserted_count, updated_count, skipped_count)

    def _get_vector(self, *, field: VectorField, asset_id: str) -> tuple[float, ...] | None:
        statement = select(asset_vectors.c.value).where(
            asset_vectors.c.repo_id == field.repo_id,
            asset_vectors.c.vector_field_id == field.vector_field_id,
            asset_vectors.c.asset_id == asset_id,
        )
        with self._engine.connect() as connection:
            value = connection.execute(statement).scalar_one_or_none()
        if value is None:
            return None
        return tuple(float(component) for component in value)

    def _validate_vector_outputs(self, *, field: VectorField, outputs: list[tuple[float, ...]]) -> None:
        if len(outputs) != len(field.validation_set):
            raise ValidationError("Complete ordered validation outputs are required")
        for output, item in zip(outputs, field.validation_set, strict=True):
            self._validate_vector(value=output, dimension=field.dimension)
            comparisons = zip(output, item.expected, strict=True)
            if any(abs(actual - expected) > field.tolerance for actual, expected in comparisons):
                raise ValidationError("Vector validation output does not match the locked validation set")

    @staticmethod
    def _validate_vector(*, value: tuple[float, ...], dimension: int) -> None:
        if len(value) != dimension or not all(math.isfinite(component) for component in value):
            raise ValidationError("Vector has invalid dimension or non-finite values")

    def _vector_field_from_row(self, row: RowMapping) -> VectorField:  # pyright: ignore[reportUnknownParameterType]
        serialized = row["validation_set"]
        validation_set = tuple(
            VectorValidationItem(bytes.fromhex(str(item["probe_hex"])), tuple(float(v) for v in item["expected"]))
            for item in serialized
        )
        return VectorField(
            str(row["vector_field_id"]),
            str(row["repo_id"]),
            str(row["name"]),
            int(row["dimension"]),
            str(row["numeric_type"]),
            str(row["distance"]),
            float(row["tolerance"]),
            validation_set,
            self,
        )

    def _open_branch(self, *, dataset: Dataset, name: str) -> DatasetView:
        self._assert_dataset_visible(dataset_id=dataset.dataset_id)
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
        return DatasetView(dataset.repo_id, dataset.dataset_id, snapshot_id, name, "branch", self)

    def _open_checkpoint(self, *, dataset: Dataset, name: str) -> DatasetView:
        self._assert_dataset_visible(dataset_id=dataset.dataset_id)
        table = self.catalog.load_table(dataset.table_identifier)
        ref = table.refs().get(name)
        if ref is None or ref.snapshot_ref_type != SnapshotRefType.TAG:
            raise ObjectNotFoundError(name)
        return DatasetView(dataset.repo_id, dataset.dataset_id, ref.snapshot_id, name, "checkpoint", self)

    def _list_checkpoints(self, *, dataset: Dataset) -> list[str]:
        self._assert_dataset_visible(dataset_id=dataset.dataset_id)
        table = self.catalog.load_table(dataset.table_identifier)
        return sorted(name for name, ref in table.refs().items() if ref.snapshot_ref_type == SnapshotRefType.TAG)

    def _create_checkpoint(self, *, dataset: Dataset, name: str, source: DatasetView) -> DatasetView:
        self._validate_view_dataset(view=source, dataset=dataset)
        if source.snapshot_id is None:
            raise ValidationError("Cannot checkpoint an empty Dataset")
        table = self.catalog.load_table(dataset.table_identifier)
        if (
            source.ref_type == "branch"
            and self._branch_snapshot_id(table=table, branch=source.ref_name) != source.snapshot_id
        ):
            raise ConflictError(source.ref_name)
        operation_id = self._start_operation(
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
        self._record_phase(operation_id=operation_id, phase="checkpoint_created")
        self._emit_operation_event(operation_id=operation_id, phase="checkpoint_created")
        self._finalize_operation(operation_id=operation_id)
        return DatasetView(dataset.repo_id, dataset.dataset_id, source.snapshot_id, name, "checkpoint", self)

    def _create_branch(self, *, dataset: Dataset, name: str, source: DatasetView) -> DatasetView:
        self._validate_view_dataset(view=source, dataset=dataset)
        if source.ref_type != "checkpoint" or source.snapshot_id is None:
            raise ValidationError("Branches can only be created from Checkpoints")
        table = self.catalog.load_table(dataset.table_identifier)
        table.manage_snapshots().create_branch(source.snapshot_id, name).commit()
        return self._open_branch(dataset=dataset, name=name)

    def _rollback(
        self,
        *,
        dataset: Dataset,
        branch: str,
        base: DatasetView,
        checkpoint: DatasetView,
    ) -> DatasetView:
        self._validate_view_dataset(view=base, dataset=dataset)
        self._validate_view_dataset(view=checkpoint, dataset=dataset)
        if base.ref_type != "branch" or base.ref_name != branch or checkpoint.ref_type != "checkpoint":
            raise ValidationError("Rollback requires target Branch View and Checkpoint View")
        if base.snapshot_id is None or checkpoint.snapshot_id is None:
            raise ValidationError("Rollback requires concrete Snapshots")
        table = self.catalog.load_table(dataset.table_identifier)
        if self._branch_snapshot_id(table=table, branch=branch) != base.snapshot_id:
            raise ConflictError(branch)
        if not self._is_ancestor(table=table, ancestor=checkpoint.snapshot_id, descendant=base.snapshot_id):
            raise ValidationError("Checkpoint is not an ancestor of the target Branch")
        operation_id = self._start_operation(
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
        self._record_phase(operation_id=operation_id, phase="rollback_published")
        self._emit_operation_event(operation_id=operation_id, phase="rollback_published")
        self._finalize_operation(operation_id=operation_id)
        return DatasetView(dataset.repo_id, dataset.dataset_id, checkpoint.snapshot_id, branch, "branch", self)

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

    def _commit(
        self,
        *,
        dataset: Dataset,
        branch: str,
        base: DatasetView,
        rows: list[dict[str, object]],
        vectors: list[VectorCommit] | None = None,
    ) -> CommitResult:
        self._validate_view_dataset(view=base, dataset=dataset)
        if base.ref_type != "branch" or base.ref_name != branch:
            raise ValidationError("Commit base must be the target Branch View")
        self._assert_dataset_visible(dataset_id=dataset.dataset_id)
        table = self.catalog.load_table(dataset.table_identifier)
        if self._branch_snapshot_id(table=table, branch=branch) != base.snapshot_id:
            raise ConflictError(branch)
        allowed_fields = {field.name for field in table.schema().fields}
        normalized_rows = [
            self._normalize_row(repo_id=dataset.repo_id, row=row, allowed_fields=allowed_fields) for row in rows
        ]
        asset_ids = [str(row["asset_id"]) for row in normalized_rows]
        if len(asset_ids) != len(set(asset_ids)):
            raise ValidationError("Duplicate asset_id in one change set")
        current_rows = self._scan_view(view=base, columns=None)
        by_id = {str(row["asset_id"]): row for row in current_rows}
        inserted = sum(asset_id not in by_id for asset_id in asset_ids)
        updated = len(asset_ids) - inserted
        for row in normalized_rows:
            by_id[str(row["asset_id"])] = row
        merged_rows = sorted(by_id.values(), key=lambda item: str(item["asset_id"]))
        pending_vectors = self._preflight_combined_vectors(
            dataset=dataset,
            candidate_asset_ids=set(by_id),
            vectors=vectors or [],
        )
        data_changed = merged_rows != sorted(current_rows, key=lambda item: str(item["asset_id"]))
        if not data_changed and not pending_vectors:
            return CommitResult(base, inserted=0, updated=0, changed=False)
        operation_id = self._start_operation(
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
        self._record_phase(operation_id=operation_id, phase="pending_vectors_written")
        self._emit_operation_event(operation_id=operation_id, phase="pending_vectors_written")
        candidate_snapshot_id = base.snapshot_id
        if data_changed:
            arrow_table = pa.Table.from_pylist(merged_rows, schema=table.schema().as_arrow())
            if base.snapshot_id is None:
                table.append(arrow_table, branch=branch)
                table = self.catalog.load_table(dataset.table_identifier)
                candidate_snapshot_id = self._branch_snapshot_id(table=table, branch=branch)
            else:
                temporary_ref = f"op_{operation_id}"
                table.manage_snapshots().create_branch(base.snapshot_id, temporary_ref).commit()
                table = self.catalog.load_table(dataset.table_identifier)
                table.overwrite(arrow_table, branch=temporary_ref)
                table = self.catalog.load_table(dataset.table_identifier)
                candidate_snapshot_id = self._branch_snapshot_id(table=table, branch=temporary_ref)
                if candidate_snapshot_id is None:
                    raise ConflictError("Temporary ref has no candidate Snapshot")
                self._update_operation_intent(
                    operation_id=operation_id,
                    values={
                        "candidate_snapshot_id": candidate_snapshot_id,
                        "temporary_ref": temporary_ref,
                    },
                )
                self._record_phase(
                    operation_id=operation_id,
                    phase="candidate_written",
                    details={"snapshot_id": candidate_snapshot_id},
                )
                self._emit_operation_event(operation_id=operation_id, phase="candidate_written")
                self._publish_candidate(
                    table_identifier=dataset.table_identifier,
                    branch=branch,
                    base_snapshot_id=base.snapshot_id,
                    candidate_snapshot_id=candidate_snapshot_id,
                    temporary_ref=temporary_ref,
                )
        self._update_operation_intent(
            operation_id=operation_id,
            values={"candidate_snapshot_id": candidate_snapshot_id},
        )
        if base.snapshot_id is None or not data_changed:
            self._record_phase(
                operation_id=operation_id,
                phase="candidate_written",
                details={"snapshot_id": candidate_snapshot_id},
            )
            self._emit_operation_event(operation_id=operation_id, phase="candidate_written")
        self._publish_pending_vectors_and_finalize(operation_id=operation_id)
        self._record_phase(operation_id=operation_id, phase="vectors_published")
        self._emit_operation_event(operation_id=operation_id, phase="vectors_published")
        view = DatasetView(dataset.repo_id, dataset.dataset_id, candidate_snapshot_id, branch, "branch", self)
        return CommitResult(view, inserted=inserted, updated=updated, changed=data_changed)

    def _preflight_combined_vectors(
        self,
        *,
        dataset: Dataset,
        candidate_asset_ids: set[str],
        vectors: list[VectorCommit],
    ) -> list[dict[str, object]]:
        field_ids = [change.field.vector_field_id for change in vectors]
        if len(field_ids) != len(set(field_ids)):
            raise ValidationError("Each VectorField may appear once in a combined commit")
        pending: list[dict[str, object]] = []
        with self._engine.connect() as connection:
            for change in vectors:
                field = change.field
                if field.repo_id != dataset.repo_id or field._manager is not self:
                    raise ValidationError("VectorField belongs to another Repo")
                self._validate_vector_outputs(field=field, outputs=change.validation_outputs)
                if not set(change.items).issubset(candidate_asset_ids):
                    raise ValidationError("Combined vectors must belong to candidate Dataset rows")
                for asset_id, value in change.items.items():
                    self._validate_vector(value=value, dimension=field.dimension)
                    exists = connection.execute(
                        select(asset_vectors.c.asset_id).where(
                            asset_vectors.c.repo_id == dataset.repo_id,
                            asset_vectors.c.vector_field_id == field.vector_field_id,
                            asset_vectors.c.asset_id == asset_id,
                        )
                    ).first()
                    if exists is not None and not change.overwrite:
                        continue
                    pending.append(
                        {
                            "repo_id": dataset.repo_id,
                            "vector_field_id": field.vector_field_id,
                            "asset_id": asset_id,
                            "value": list(value),
                        }
                    )
        return pending

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
        actual = self._branch_snapshot_id(table=table, branch=branch)
        if actual == candidate_snapshot_id:
            if temporary_ref in table.refs():
                table.manage_snapshots().remove_branch(temporary_ref).commit()
            return
        if actual != base_snapshot_id:
            raise ConflictError(branch)
        table.manage_snapshots().create_branch(candidate_snapshot_id, branch).remove_branch(temporary_ref).commit()

    def _normalize_row(
        self,
        *,
        repo_id: str,
        row: dict[str, object],
        allowed_fields: set[str],
    ) -> dict[str, object]:
        if not _SYSTEM_FIELDS.issubset(row) or not set(row).issubset(allowed_fields):
            raise ValidationError(
                f"Row fields must include system fields and match Physical Schema: {sorted(allowed_fields)}"
            )
        asset_id = row["asset_id"]
        prefix_id = row["storage_prefix_id"]
        relative_path = row["relative_path"]
        if not isinstance(asset_id, str) or _ASSET_ID_PATTERN.fullmatch(asset_id) is None:
            raise ValidationError("asset_id must be normalized SHA-256")
        if not isinstance(prefix_id, str) or not isinstance(relative_path, str):
            raise ValidationError("Storage position must use string fields")
        if not self._repo_has_prefix(repo_id=repo_id, prefix_id=prefix_id):
            raise StorageAuthorizationError(prefix_id)
        self.storage_manager.verify(StoredObject(asset_id, prefix_id, relative_path))
        tag_value = row["tag_ids"]
        if not isinstance(tag_value, list) or not all(isinstance(tag_id, str) for tag_id in tag_value):
            raise ValidationError("tag_ids must be a list of strings")
        tag_ids = sorted(set(tag_value))
        self._validate_active_tags(repo_id=repo_id, tag_ids=tag_ids)
        source_uri = row["source_uri"]
        if source_uri is not None and not isinstance(source_uri, str):
            raise ValidationError("source_uri must be string or None")
        normalized: dict[str, object] = {
            "asset_id": asset_id,
            "storage_prefix_id": prefix_id,
            "relative_path": relative_path,
            "source_uri": source_uri,
            "tag_ids": tag_ids,
        }
        normalized.update({key: value for key, value in row.items() if key not in _SYSTEM_FIELDS})
        return normalized

    def _add_column(
        self,
        *,
        dataset: Dataset,
        branch: str,
        base: DatasetView,
        name: str,
        field_type: str,
    ) -> DatasetView:
        self._validate_view_dataset(view=base, dataset=dataset)
        if base.ref_type != "branch" or base.ref_name != branch:
            raise ValidationError("Schema baseline must be the target Branch View")
        table = self.catalog.load_table(dataset.table_identifier)
        if self._branch_snapshot_id(table=table, branch=branch) != base.snapshot_id:
            raise ConflictError(branch)
        normalized_name = name.strip()
        if not normalized_name or normalized_name in _SYSTEM_FIELDS:
            raise ValidationError("System fields cannot be changed")
        type_factory = _BUSINESS_FIELD_TYPES.get(field_type)
        if type_factory is None:
            raise ValidationError(f"Unsupported Physical Schema type: {field_type}")
        try:
            table.update_schema().add_column(normalized_name, type_factory(), required=False).commit()
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return self._open_branch(dataset=dataset, name=branch)

    def _scan_view(self, *, view: DatasetView, columns: list[str] | None) -> list[dict[str, object]]:
        dataset = self._dataset_by_id(repo_id=view.repo_id, dataset_id=view.dataset_id)
        table = self.catalog.load_table(dataset.table_identifier)
        known_columns = {field.name for field in table.schema().fields}
        if columns is not None and not set(columns).issubset(known_columns):
            raise ValidationError("Unknown Physical Schema column")
        if view.snapshot_id is None:
            return []
        selected = tuple(columns) if columns is not None else ("*",)
        arrow_table = table.scan(snapshot_id=view.snapshot_id, selected_fields=selected).to_arrow()
        return arrow_table.to_pylist()

    def _get_view_row(self, *, view: DatasetView, asset_id: str) -> dict[str, object]:
        rows = [row for row in self._scan_view(view=view, columns=None) if row["asset_id"] == asset_id]
        if not rows:
            raise ObjectNotFoundError(asset_id)
        return rows[0]

    def _read_view_image(self, *, view: DatasetView, asset_id: str) -> bytes:
        row = self._get_view_row(view=view, asset_id=asset_id)
        return self.storage_manager.read_bytes(
            prefix_id=str(row["storage_prefix_id"]),
            relative_path=str(row["relative_path"]),
        )

    def _verify_view_image(self, *, view: DatasetView, asset_id: str) -> bool:
        row = self._get_view_row(view=view, asset_id=asset_id)
        return self.storage_manager.verify(
            StoredObject(
                asset_id=str(row["asset_id"]),
                storage_prefix_id=str(row["storage_prefix_id"]),
                relative_path=str(row["relative_path"]),
            )
        )

    def _branch_snapshot_id(
        self,
        *,
        table: Table,  # pyright: ignore[reportUnknownParameterType]
        branch: str,
    ) -> int | None:
        refs = table.refs()
        if branch == "main" and branch not in refs:
            current = table.current_snapshot()
            return current.snapshot_id if current is not None else None
        ref = refs.get(branch)
        if ref is None or ref.snapshot_ref_type != SnapshotRefType.BRANCH:
            raise ObjectNotFoundError(branch)
        return ref.snapshot_id

    def _validate_view_dataset(self, *, view: DatasetView, dataset: Dataset) -> None:
        if view.repo_id != dataset.repo_id or view.dataset_id != dataset.dataset_id or view._manager is not self:
            raise ValidationError("DatasetView belongs to another Dataset or Repo")

    def _repo_has_prefix(self, *, repo_id: str, prefix_id: str) -> bool:
        statement = select(repo_storage_bindings).where(
            repo_storage_bindings.c.repo_id == repo_id,
            repo_storage_bindings.c.prefix_id == prefix_id,
        )
        with self._engine.connect() as connection:
            return connection.execute(statement).first() is not None

    def _validate_active_tags(self, *, repo_id: str, tag_ids: list[str]) -> None:
        if not tag_ids:
            return
        statement = select(tag_definitions.c.tag_id).where(
            tag_definitions.c.repo_id == repo_id,
            tag_definitions.c.tag_id.in_(tag_ids),
            tag_definitions.c.archived.is_(False),
        )
        with self._engine.connect() as connection:
            found = set(connection.execute(statement).scalars())
        if found != set(tag_ids):
            raise ValidationError("Unknown or archived tag_id")

    def _dataset_by_id(self, *, repo_id: str, dataset_id: str) -> Dataset:
        statement = select(datasets).where(datasets.c.repo_id == repo_id, datasets.c.dataset_id == dataset_id)
        with self._engine.connect() as connection:
            row = connection.execute(statement).mappings().one_or_none()
        if row is None:
            raise ObjectNotFoundError(dataset_id)
        return self._dataset_from_row(row)

    def _repo_from_row(self, row: RowMapping) -> DatasetRepo:  # pyright: ignore[reportUnknownParameterType]
        return DatasetRepo(
            repo_id=str(row["repo_id"]),
            name=str(row["name"]),
            namespace=str(row["namespace"]),
            _manager=self,
        )

    def _dataset_from_row(self, row: RowMapping) -> Dataset:  # pyright: ignore[reportUnknownParameterType]
        return Dataset(
            repo_id=str(row["repo_id"]),
            dataset_id=str(row["dataset_id"]),
            name=str(row["name"]),
            table_identifier=str(row["table_identifier"]),
            _manager=self,
        )
