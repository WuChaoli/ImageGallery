import pytest
from sqlalchemy import create_engine, inspect, text

from image_gallery.dataset_manager.migrations import upgrade_control_database

pytestmark = pytest.mark.dataset_backend


def test_postgres_migration_creates_isolated_schemas_and_relations(dataset_postgres_url: str) -> None:
    engine = create_engine(dataset_postgres_url)

    upgrade_control_database(engine)

    inspector = inspect(engine)
    assert {"control", "vectors", "iceberg_catalog"} <= set(inspector.get_schema_names())
    assert set(inspector.get_table_names(schema="control")) == {
        "alembic_version",
        "datasets",
        "model_definitions",
        "operation_phases",
        "operations",
        "repo_storage_bindings",
        "repos",
        "storage_prefixes",
        "tag_definitions",
        "vector_fields",
    }
    assert set(inspector.get_table_names(schema="vectors")) == {
        "asset_vectors",
        "pending_asset_vectors",
    }
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")) == "vector"
        roles = set(connection.scalars(text("SELECT rolname FROM pg_roles WHERE rolname LIKE 'dataset_manager_%'")))
        assert roles == {
            "dataset_manager_catalog",
            "dataset_manager_control",
            "dataset_manager_vectors",
        }
        assert connection.scalar(
            text("SELECT has_table_privilege('dataset_manager_vectors', 'vectors.pending_asset_vectors', 'DELETE')")
        )
        assert connection.scalar(text("SELECT pg_has_role(current_user, 'dataset_manager_vectors', 'MEMBER')"))
