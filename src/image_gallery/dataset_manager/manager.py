"""DatasetManager Backend 生命周期入口。"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
from pyiceberg.catalog import Catalog, load_catalog
from pyiceberg.schema import Schema
from pyiceberg.table import Table
from pyiceberg.types import ListType, NestedField, StringType
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from image_gallery.dataset_manager._dataset_history import DatasetHistory
from image_gallery.dataset_manager._embedding import EmbeddingService
from image_gallery.dataset_manager._history_lock import DatasetHistoryLock
from image_gallery.dataset_manager._operation_journal import OperationJournal
from image_gallery.dataset_manager._physical_schema import (
    ColumnSpec,
    FieldType,
    canonicalize_value,
    column_spec_from_iceberg,
    iceberg_type_for_addition,
)
from image_gallery.dataset_manager._repository_store import DatasetRecord, RepositoryRecord, RepositoryStore
from image_gallery.dataset_manager._schema_lock import RepoSchemaLock
from image_gallery.dataset_manager._tag_store import TagRecord, TagStore
from image_gallery.dataset_manager._vector_store import VectorFieldRecord, VectorStore
from image_gallery.dataset_manager._view_io import ViewIO
from image_gallery.dataset_manager.control import metadata
from image_gallery.dataset_manager.errors import (
    ConflictError,
    NameConflictError,
    ObjectNotFoundError,
    StorageAuthorizationError,
    ValidationError,
)
from image_gallery.dataset_manager.migrations import upgrade_control_database
from image_gallery.dataset_manager.models import (
    CommitMode,
    CommitResult,
    Dataset,
    DatasetRepo,
    DatasetView,
    EmbedResult,
    TagDefinition,
    VectorField,
)
from image_gallery.model_manager import ModelManager
from image_gallery.storage_manager import StorageManager, StoredObject

SYSTEM_SCHEMA = Schema(
    NestedField(1, "asset_id", StringType(), required=True),
    NestedField(2, "storage_prefix_id", StringType(), required=True),
    NestedField(3, "relative_path", StringType(), required=True),
    NestedField(4, "source_uri", StringType(), required=False),
    NestedField(5, "tag_ids", ListType(6, StringType(), element_required=True), required=True),
    identifier_field_ids=[1],
)
_ASSET_ID_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_SYSTEM_FIELDS = {"asset_id", "storage_prefix_id", "relative_path", "source_uri", "tag_ids"}


def _schema_name_key(name: str) -> str:
    """返回普通列与 VectorField 共享的名称冲突键。"""
    return name.strip().casefold()


class DatasetManager:
    """管理 DatasetRepo 的连接与生命周期。"""

    def __init__(
        self,
        *,
        control_engine: Engine,  # pyright: ignore[reportUnknownParameterType]
        catalog: Catalog,  # pyright: ignore[reportUnknownParameterType]
        storage_manager: StorageManager,
        model_manager: ModelManager | None = None,
        operation_hook: Callable[[str, str], None] | None = None,
        owns_engine: bool = False,
        owns_catalog: bool = False,
    ) -> None:
        """使用显式 Backend 组合创建 DatasetManager。"""
        self._engine = control_engine
        self.catalog = catalog
        self.storage_manager = storage_manager
        self._owns_engine = owns_engine
        self._owns_catalog = owns_catalog
        self._owns_model_manager = model_manager is None
        self._closed = False
        if self._engine.dialect.name == "postgresql":
            upgrade_control_database(self._engine)
        else:
            metadata.create_all(self._engine)
        self.model_manager = model_manager or ModelManager()
        self.model_manager.bind_engine(control_engine)
        self._operations = OperationJournal(control_engine, operation_hook=operation_hook)
        self._repositories = RepositoryStore(control_engine, storage_manager=storage_manager)
        self._repositories.restore_storage_prefixes()
        self._tags = TagStore(control_engine)
        self._vectors = VectorStore(control_engine)
        self._schema_lock = RepoSchemaLock(control_engine)
        self._history_lock = DatasetHistoryLock(control_engine)
        self._view_io = ViewIO(
            catalog=catalog,
            storage_manager=storage_manager,
            repositories=self._repositories,
            vectors=self._vectors,
        )
        self._embedding = EmbeddingService(
            storage_manager=storage_manager,
            model_manager=self.model_manager,
            vectors=self._vectors,
            view_io=self._view_io,
        )
        self._history = DatasetHistory(
            manager=self,
            engine=control_engine,
            catalog=catalog,
            storage_manager=storage_manager,
            operations=self._operations,
            repositories=self._repositories,
            system_schema=SYSTEM_SCHEMA,
            system_fields=_SYSTEM_FIELDS,
            history_lock=self._history_lock,
            schema_lock=self._schema_lock,
        )

    @classmethod
    def local(
        cls,
        *,
        root: str | Path,
        storage_manager: StorageManager,
        model_manager: ModelManager | None = None,
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
            model_manager=model_manager,
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
        model_manager: ModelManager | None = None,
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
            model_manager=model_manager,
            operation_hook=operation_hook,
            owns_engine=True,
            owns_catalog=True,
        )

    def close(self) -> None:
        """释放由 DatasetManager factory 创建的数据库连接池。"""
        if self._closed:
            return
        self._closed = True
        try:
            if self._owns_model_manager:
                self.model_manager.close()
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
            self._repositories.add_repo(record=RepositoryRecord(repo_id=repo_id, name=name, namespace=namespace))
        except IntegrityError as exc:
            self.catalog.drop_namespace(namespace)
            raise NameConflictError(name) from exc
        return DatasetRepo(repo_id=repo_id, name=name, namespace=namespace, _manager=self)

    def open_repo(self, *, name: str) -> DatasetRepo:
        """按大小写不敏感名称打开 DatasetRepo。"""
        return self._repo_from_record(self._repositories.get_repo_by_name(name=name))

    def list_repos(self) -> list[DatasetRepo]:
        """按名称返回全部 DatasetRepo。"""
        return [self._repo_from_record(record) for record in self._repositories.list_repos()]

    def _create_dataset(self, *, repo: DatasetRepo, name: str) -> Dataset:
        dataset_id = uuid.uuid4().hex
        table_identifier = f"{repo.namespace}.d_{dataset_id[:12]}"
        operation_id = self._operations.start(
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
            self._operations.record_phase(operation_id=operation_id, phase="table_created")
            self._repositories.register_dataset(
                operation_id=operation_id,
                record=DatasetRecord(
                    repo_id=repo.repo_id,
                    dataset_id=dataset_id,
                    name=name,
                    table_identifier=table_identifier,
                ),
                name_key=name.casefold(),
            )
        except IntegrityError as exc:
            self._operations.fail(operation_id=operation_id)
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
        return self._history.recover_operations()

    def _assert_dataset_visible(self, *, dataset_id: str) -> None:
        self._history.assert_dataset_visible(dataset_id=dataset_id)

    def _open_dataset(self, *, repo: DatasetRepo, name: str) -> Dataset:
        return self._dataset_from_record(self._repositories.get_dataset_by_name(repo_id=repo.repo_id, name=name))

    def _list_datasets(self, *, repo: DatasetRepo) -> list[Dataset]:
        return [self._dataset_from_record(record) for record in self._repositories.list_datasets(repo_id=repo.repo_id)]

    def _bind_storage_prefix(self, *, repo: DatasetRepo, prefix_id: str) -> None:
        self._repositories.bind_storage_prefix(repo_id=repo.repo_id, prefix_id=prefix_id)

    def _list_storage_prefix_ids(self, *, repo: DatasetRepo) -> list[str]:
        return self._repositories.list_storage_prefix_ids(repo_id=repo.repo_id)

    def _create_tag(
        self,
        *,
        repo: DatasetRepo,
        name: str,
        color: str | None,
        description: str | None,
    ) -> TagDefinition:
        record = self._tags.create(
            repo_id=repo.repo_id,
            name=name,
            color=color,
            description=description,
        )
        return self._tag_from_record(record)

    def _rename_tag(self, *, repo: DatasetRepo, tag_id: str, name: str) -> TagDefinition:
        return self._tag_from_record(self._tags.rename(repo_id=repo.repo_id, tag_id=tag_id, name=name))

    def _archive_tag(self, *, repo: DatasetRepo, tag_id: str) -> TagDefinition:
        return self._tag_from_record(self._tags.archive(repo_id=repo.repo_id, tag_id=tag_id))

    def _create_bound_vector_field(
        self,
        *,
        repo: DatasetRepo,
        name: str,
        model_id: str,
        distance: str,
    ) -> VectorField:
        with self._repo_schema_lock(repo_id=repo.repo_id):
            return self._create_bound_vector_field_locked(
                repo=repo,
                name=name,
                model_id=model_id,
                distance=distance,
            )

    def _create_bound_vector_field_locked(
        self,
        *,
        repo: DatasetRepo,
        name: str,
        model_id: str,
        distance: str,
    ) -> VectorField:
        """在已持有 Repo Schema 锁时创建 VectorField。"""
        normalized_name = name.strip()
        name_key = _schema_name_key(name)
        if not name_key:
            raise ValidationError("VectorField name cannot be empty")
        if distance not in {"cosine", "dot", "l2"}:
            raise ValidationError("VectorField requires a supported distance")
        for dataset in self._list_datasets(repo=repo):
            if name_key in {_schema_name_key(column.name) for column in self._list_columns(dataset=dataset)}:
                raise ValidationError(f"VectorField conflicts with Physical Schema column: {normalized_name}")
        definition = self.model_manager.get(model_id=model_id)
        if definition is None:
            raise ValidationError(f"Unknown model_id: {model_id}")
        existing = None
        try:
            existing = self._open_vector_field(repo=repo, name=normalized_name)
        except ObjectNotFoundError:
            pass
        if existing is not None:
            if (
                existing.model_id == model_id
                and existing.model_fingerprint == definition.fingerprint
                and existing.distance == distance
            ):
                return existing
            raise NameConflictError(normalized_name)
        return self._vector_field_from_record(
            self._vectors.create(
                repo_id=repo.repo_id,
                name=normalized_name,
                name_key=name_key,
                model_id=model_id,
                model_fingerprint=definition.fingerprint,
                dimension=definition.dimension,
                numeric_type=definition.dtype,
                distance=distance,
            )
        )

    def _open_vector_field(self, *, repo: DatasetRepo, name: str) -> VectorField:
        return self._vector_field_from_record(
            self._vectors.find_by_name(
                repo_id=repo.repo_id,
                name_key=_schema_name_key(name),
                requested_name=name,
            )
        )

    def _get_vector_field(self, *, repo: DatasetRepo, vector_field_id: str) -> VectorField:
        return self._vector_field_from_record(
            self._vectors.find_by_id(repo_id=repo.repo_id, vector_field_id=vector_field_id)
        )

    def _list_vector_fields(self, *, repo: DatasetRepo) -> list[VectorField]:
        return [self._vector_field_from_record(record) for record in self._vectors.list(repo_id=repo.repo_id)]

    def _clone_dataset(self, *, repo: DatasetRepo, source: DatasetView, name: str) -> Dataset:
        return self._history.clone_dataset(repo=repo, source=source, name=name)

    def _get_vector(self, *, field: VectorField, asset_id: str) -> tuple[float, ...] | None:
        return self._vectors.get_current(
            repo_id=field.repo_id,
            vector_field_id=field.vector_field_id,
            asset_id=asset_id,
        )

    def _vector_field_from_record(self, record: VectorFieldRecord) -> VectorField:
        return VectorField(
            record.vector_field_id,
            record.repo_id,
            record.name,
            record.model_id,
            record.model_fingerprint,
            record.dimension,
            record.numeric_type,
            record.distance,
            self,
        )

    def _open_branch(self, *, dataset: Dataset, name: str) -> DatasetView:
        return self._history.open_branch(dataset=dataset, name=name)

    def _open_checkpoint(self, *, dataset: Dataset, name: str) -> DatasetView:
        return self._history.open_checkpoint(dataset=dataset, name=name)

    def _list_checkpoints(self, *, dataset: Dataset) -> list[str]:
        return self._history.list_checkpoints(dataset=dataset)

    def _create_checkpoint(self, *, dataset: Dataset, name: str, source: DatasetView) -> DatasetView:
        return self._history.create_checkpoint(dataset=dataset, name=name, source=source)

    def _create_branch(self, *, dataset: Dataset, name: str, source: DatasetView) -> DatasetView:
        return self._history.create_branch(dataset=dataset, name=name, source=source)

    def _view_owner_dataset(self, *, view: DatasetView) -> Dataset:
        """按 View 的不可变 ID 解析可见 Dataset。"""
        if view._manager is not self:
            raise ValidationError("DatasetView belongs to another DatasetManager")
        self._assert_dataset_visible(dataset_id=view.dataset_id)
        return self._dataset_by_id(repo_id=view.repo_id, dataset_id=view.dataset_id)

    def _view_owner_repo(self, *, view: DatasetView) -> DatasetRepo:
        """按 View 的不可变 ID 解析可见 DatasetRepo。"""
        dataset = self._view_owner_dataset(view=view)
        return self._repo_by_id(dataset.repo_id)

    def _rollback(
        self,
        *,
        dataset: Dataset,
        branch: str,
        base: DatasetView,
        checkpoint: DatasetView,
    ) -> DatasetView:
        return self._history.rollback(dataset=dataset, branch=branch, base=base, checkpoint=checkpoint)

    def _commit(
        self,
        *,
        dataset: Dataset,
        branch: str,
        base: DatasetView,
        frame: pd.DataFrame,
        mode: CommitMode,
        fields: list[str] | None,
        schema_additions: list[ColumnSpec] | tuple[ColumnSpec, ...],
        checkpoint_name: str | None,
    ) -> CommitResult:
        if schema_additions:
            with self._schema_lock.hold(repo_id=dataset.repo_id):
                with self._history_lock.hold(dataset_id=dataset.dataset_id):
                    return self._history.commit(
                        dataset=dataset,
                        branch=branch,
                        base=base,
                        frame=frame,
                        mode=mode,
                        fields=fields,
                        schema_additions=schema_additions,
                        checkpoint_name=checkpoint_name,
                    )
        with self._history_lock.hold(dataset_id=dataset.dataset_id):
            return self._history.commit(
                dataset=dataset,
                branch=branch,
                base=base,
                frame=frame,
                mode=mode,
                fields=fields,
                schema_additions=schema_additions,
                checkpoint_name=checkpoint_name,
            )

    def _commit_rows(
        self,
        *,
        dataset: Dataset,
        branch: str,
        base: DatasetView,
        rows: list[dict[str, object]],
    ) -> CommitResult:
        return self._history.commit_rows(dataset=dataset, branch=branch, base=base, rows=rows)

    def _normalize_row(
        self,
        *,
        repo_id: str,
        row: dict[str, object],
        allowed_fields: set[str],
        column_specs: dict[str, ColumnSpec] | None = None,
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
        for key, value in row.items():
            if key in _SYSTEM_FIELDS:
                continue
            spec = None if column_specs is None else column_specs.get(key)
            normalized[key] = (
                value if spec is None else canonicalize_value(spec.field_type, value, required=spec.required, path=key)
            )
        if column_specs is not None:
            for key, spec in column_specs.items():
                if key not in normalized and key not in _SYSTEM_FIELDS:
                    normalized[key] = canonicalize_value(spec.field_type, None, required=spec.required, path=key)
        return normalized

    def _add_column(
        self,
        *,
        dataset: Dataset,
        branch: str,
        base: DatasetView,
        column: ColumnSpec | None,
        name: str | None,
        field_type: FieldType | str | None,
    ) -> DatasetView:
        resolved = self._resolve_column_spec(column=column, name=name, field_type=field_type)
        with self._repo_schema_lock(repo_id=dataset.repo_id):
            with self._history_lock.hold(dataset_id=dataset.dataset_id):
                return self._add_column_locked(dataset=dataset, branch=branch, base=base, column=resolved)

    def _add_column_locked(
        self,
        *,
        dataset: Dataset,
        branch: str,
        base: DatasetView,
        column: ColumnSpec,
    ) -> DatasetView:
        """在已持有 Repo Schema 锁时新增普通列。"""
        self._validate_view_dataset(view=base, dataset=dataset)
        if base.ref_type != "branch" or base.ref_name != branch:
            raise ValidationError("Schema baseline must be the target Branch View")
        table = self.catalog.load_table(dataset.table_identifier)
        if self._branch_snapshot_id(table=table, branch=branch) != base.snapshot_id:
            raise ConflictError(branch)
        if column.required:
            raise ValidationError("Business columns must be optional")
        normalized_name = column.name
        if not normalized_name or normalized_name in _SYSTEM_FIELDS:
            raise ValidationError("System fields cannot be changed")
        repo = self._repo_by_id(dataset.repo_id)
        if _schema_name_key(normalized_name) in {
            _schema_name_key(field.name) for field in self._list_vector_fields(repo=repo)
        }:
            raise ValidationError(f"Physical Schema column conflicts with VectorField: {normalized_name}")
        existing_columns = {field.name: column_spec_from_iceberg(field) for field in table.schema().fields}
        same_name = next(
            (item for name, item in existing_columns.items() if name.casefold() == normalized_name.casefold()),
            None,
        )
        if same_name is not None:
            if same_name == column:
                return base
            raise ValidationError(f"Physical Schema column conflicts: {normalized_name}")
        try:
            operation_id = self._operations.start(
                kind="schema",
                repo_id=dataset.repo_id,
                dataset_id=dataset.dataset_id,
                intent={
                    "repo_id": dataset.repo_id,
                    "dataset_id": dataset.dataset_id,
                    "table_identifier": dataset.table_identifier,
                    "branch": branch,
                    "base_snapshot_id": base.snapshot_id,
                    "column": column.to_dict(),
                },
            )
            table.update_schema().add_column(
                normalized_name,
                iceberg_type_for_addition(column.field_type),
                required=False,
            ).commit()
            self._operations.record_phase(operation_id=operation_id, phase="schema_updated")
            self._operations.finalize(operation_id=operation_id)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return self._open_branch(dataset=dataset, name=branch)

    @staticmethod
    def _resolve_column_spec(
        *,
        column: ColumnSpec | None,
        name: str | None,
        field_type: FieldType | str | None,
    ) -> ColumnSpec:
        """统一 typed ColumnSpec 与旧标量参数入口。"""
        if column is not None:
            if name is not None or field_type is not None:
                raise ValidationError("column cannot be combined with name or field_type")
            return column
        if name is None or field_type is None:
            raise ValidationError("name and field_type are required when column is omitted")
        return ColumnSpec(name=name, field_type=field_type)

    @contextmanager
    def _repo_schema_lock(self, *, repo_id: str):  # pyright: ignore[reportUnknownParameterType]
        """在同一 Repo 的跨 facade Schema 修改期间持有互斥锁。"""
        with self._schema_lock.hold(repo_id=repo_id):
            yield

    def _list_columns(self, *, dataset: Dataset) -> list[ColumnSpec]:
        self._history.assert_dataset_visible(dataset_id=dataset.dataset_id)
        table = self.catalog.load_table(dataset.table_identifier)
        return [column_spec_from_iceberg(field) for field in table.schema().fields]

    def _scan_view_frame(self, *, view: DatasetView, fields: list[str] | None) -> pd.DataFrame:
        self._history.assert_fixed_view_readable(dataset_id=view.dataset_id)
        return self._view_io.scan_frame(view=view, fields=fields)

    def _get_view_row_series(  # pyright: ignore[reportMissingTypeArgument, reportUnknownParameterType]
        self,
        *,
        view: DatasetView,
        asset_id: str,
        fields: list[str] | None,
    ) -> pd.Series:
        self._history.assert_fixed_view_readable(dataset_id=view.dataset_id)
        return self._view_io.get_row_series(view=view, asset_id=asset_id, fields=fields)

    def _generate_embed(
        self,
        *,
        dataset: Dataset,
        field_name: str,
        source: DatasetView | None,
        branch: str,
        overwrite: bool,
    ) -> EmbedResult:
        if source is not None and branch != "main":
            raise ValidationError("source and non-default branch are mutually exclusive")
        view = source or self._open_branch(dataset=dataset, name=branch)
        self._validate_view_dataset(view=view, dataset=dataset)
        repo = self._repo_by_id(dataset.repo_id)
        field = self._open_vector_field(repo=repo, name=field_name)
        definition = self.model_manager.get(model_id=field.model_id)
        if definition is None:
            raise ValidationError(f"Unknown model_id: {field.model_id}")
        if definition.fingerprint != field.model_fingerprint:
            raise ValidationError("VectorField model fingerprint does not match registered model")
        return self._embedding.generate(
            dataset=dataset,
            field=field,
            view=view,
            overwrite=overwrite,
        )

    def _scan_view(self, *, view: DatasetView, columns: list[str] | None) -> list[dict[str, object]]:
        self._history.assert_fixed_view_readable(dataset_id=view.dataset_id)
        return self._view_io.scan(view=view, columns=columns)

    def _get_view_row(self, *, view: DatasetView, asset_id: str) -> dict[str, object]:
        return self._view_io.get_row(view=view, asset_id=asset_id)

    def _read_view_image(self, *, view: DatasetView, asset_id: str) -> bytes:
        self._history.assert_fixed_view_readable(dataset_id=view.dataset_id)
        return self._view_io.read_image(view=view, asset_id=asset_id)

    def _verify_view_image(self, *, view: DatasetView, asset_id: str) -> bool:
        self._history.assert_fixed_view_readable(dataset_id=view.dataset_id)
        return self._view_io.verify_image(view=view, asset_id=asset_id)

    def _branch_snapshot_id(
        self,
        *,
        table: Table,  # pyright: ignore[reportUnknownParameterType]
        branch: str,
    ) -> int | None:
        return self._history.branch_snapshot_id(table=table, branch=branch)

    def _validate_view_dataset(self, *, view: DatasetView, dataset: Dataset) -> None:
        if view.repo_id != dataset.repo_id or view.dataset_id != dataset.dataset_id or view._manager is not self:
            raise ValidationError("DatasetView belongs to another Dataset or Repo")

    def _repo_has_prefix(self, *, repo_id: str, prefix_id: str) -> bool:
        return self._repositories.has_storage_prefix(repo_id=repo_id, prefix_id=prefix_id)

    def _validate_active_tags(self, *, repo_id: str, tag_ids: list[str]) -> None:
        self._tags.validate_active(repo_id=repo_id, tag_ids=tag_ids)

    def _dataset_by_id(self, *, repo_id: str, dataset_id: str) -> Dataset:
        return self._dataset_from_record(self._repositories.get_dataset(repo_id=repo_id, dataset_id=dataset_id))

    def _repo_by_id(self, repo_id: str) -> DatasetRepo:
        return self._repo_from_record(self._repositories.get_repo(repo_id=repo_id))

    @staticmethod
    def _tag_from_record(record: TagRecord) -> TagDefinition:
        return TagDefinition(
            record.tag_id,
            record.repo_id,
            record.name,
            record.color,
            record.description,
            record.archived,
        )

    def _repo_from_record(self, record: RepositoryRecord) -> DatasetRepo:
        return DatasetRepo(
            repo_id=record.repo_id,
            name=record.name,
            namespace=record.namespace,
            _manager=self,
        )

    def _dataset_from_record(self, record: DatasetRecord) -> Dataset:
        return Dataset(
            repo_id=record.repo_id,
            dataset_id=record.dataset_id,
            name=record.name,
            table_identifier=record.table_identifier,
            _manager=self,
        )
