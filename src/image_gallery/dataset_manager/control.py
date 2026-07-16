"""DatasetManager 控制面关系模型。"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()

repos = Table(
    "repos",
    metadata,
    Column("repo_id", String(32), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("name_key", String(255), nullable=False, unique=True),
    Column("namespace", String(255), nullable=False, unique=True),
    schema="control",
)

datasets = Table(
    "datasets",
    metadata,
    Column("dataset_id", String(32), primary_key=True),
    Column("repo_id", String(32), ForeignKey("control.repos.repo_id"), nullable=False),
    Column("name", String(255), nullable=False),
    Column("name_key", String(255), nullable=False),
    Column("table_identifier", String(511), nullable=False, unique=True),
    UniqueConstraint("repo_id", "name_key", name="uq_datasets_repo_name_key"),
    schema="control",
)

operations = Table(
    "operations",
    metadata,
    Column("operation_id", String(32), primary_key=True),
    Column("repo_id", String(32), ForeignKey("control.repos.repo_id"), nullable=False),
    # create_dataset 的 durable intent 先于 Dataset 行写入，不能在这里建立外键。
    Column("dataset_id", String(32), nullable=True),
    Column("kind", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("intent", JSON, nullable=False),
    schema="control",
)

operation_phases = Table(
    "operation_phases",
    metadata,
    Column(
        "operation_id",
        String(32),
        ForeignKey("control.operations.operation_id"),
        primary_key=True,
    ),
    Column("phase", String(64), primary_key=True),
    Column("status", String(32), nullable=False),
    Column("details", JSON, nullable=True),
    schema="control",
)

repo_storage_bindings = Table(
    "repo_storage_bindings",
    metadata,
    Column("repo_id", String(32), ForeignKey("control.repos.repo_id"), primary_key=True),
    Column("prefix_id", String(64), primary_key=True),
    schema="control",
)

tag_definitions = Table(
    "tag_definitions",
    metadata,
    Column("tag_id", String(32), primary_key=True),
    Column("repo_id", String(32), ForeignKey("control.repos.repo_id"), nullable=False),
    Column("name", String(255), nullable=False),
    Column("name_key", String(255), nullable=False),
    Column("color", String(32), nullable=True),
    Column("description", String(1024), nullable=True),
    Column("archived", Boolean, nullable=False, default=False),
    UniqueConstraint("repo_id", "name_key", name="uq_tags_repo_name_key"),
    schema="control",
)

vector_fields = Table(
    "vector_fields",
    metadata,
    Column("vector_field_id", String(32), primary_key=True),
    Column("repo_id", String(32), ForeignKey("control.repos.repo_id"), nullable=False),
    Column("name", String(255), nullable=False),
    Column("name_key", String(255), nullable=False),
    Column("dimension", Integer, nullable=False),
    Column("numeric_type", String(32), nullable=False),
    Column("distance", String(32), nullable=False),
    Column("tolerance", Float, nullable=False),
    Column("validation_set", JSON, nullable=False),
    UniqueConstraint("repo_id", "name_key", name="uq_vector_fields_repo_name_key"),
    schema="control",
)

vector_validation_items = Table(
    "vector_validation_items",
    metadata,
    Column(
        "vector_field_id",
        String(32),
        ForeignKey("control.vector_fields.vector_field_id"),
        primary_key=True,
    ),
    Column("position", Integer, primary_key=True),
    Column("probe", LargeBinary, nullable=False),
    Column("probe_hash", String(71), nullable=False),
    Column("expected", JSON, nullable=False),
    schema="control",
)

asset_vectors = Table(
    "asset_vectors",
    metadata,
    Column("repo_id", String(32), ForeignKey("control.repos.repo_id"), primary_key=True),
    Column(
        "vector_field_id",
        String(32),
        ForeignKey("control.vector_fields.vector_field_id"),
        primary_key=True,
    ),
    Column("asset_id", String(71), primary_key=True),
    Column("value", Vector().with_variant(JSON(), "sqlite"), nullable=False),
    schema="vectors",
)

pending_asset_vectors = Table(
    "pending_asset_vectors",
    metadata,
    Column(
        "operation_id",
        String(32),
        ForeignKey("control.operations.operation_id"),
        primary_key=True,
    ),
    Column("repo_id", String(32), ForeignKey("control.repos.repo_id"), primary_key=True),
    Column(
        "vector_field_id",
        String(32),
        ForeignKey("control.vector_fields.vector_field_id"),
        primary_key=True,
    ),
    Column("asset_id", String(71), primary_key=True),
    Column("value", Vector().with_variant(JSON(), "sqlite"), nullable=False),
    schema="vectors",
)
