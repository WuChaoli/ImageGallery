import threading
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, insert, inspect, select, text
from sqlalchemy.exc import IntegrityError

from image_gallery.dataset_manager import DatasetManager
from image_gallery.dataset_manager import migrations as dataset_migrations
from image_gallery.dataset_manager.control import (
    asset_vectors,
    dataset_name_reservations,
    datasets,
    operations,
    pending_asset_vectors,
    repos,
    vector_fields,
)
from image_gallery.dataset_manager.migrations import upgrade_control_database
from image_gallery.model_manager import ModelManager
from image_gallery.storage_manager import StorageManager

pytestmark = pytest.mark.dataset_backend


def _upgrade_revision(engine, revision: str) -> None:  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    config = Config()
    config.set_main_option("script_location", str(Path(dataset_migrations.__file__).with_name("alembic")))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


def _reset_to_0001(engine) -> None:  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS vectors CASCADE"))
        connection.execute(text("DROP SCHEMA IF EXISTS control CASCADE"))
    _upgrade_revision(engine, "0001_dataset_manager_mvp")
    # 0001 使用当前 metadata.create_all；移除未来关系以模拟真实旧部署。
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE control.dataset_name_reservations"))


def test_postgres_migration_creates_isolated_schemas_and_relations(dataset_postgres_url: str) -> None:
    engine = create_engine(dataset_postgres_url)

    upgrade_control_database(engine)

    inspector = inspect(engine)
    assert {"control", "vectors", "iceberg_catalog"} <= set(inspector.get_schema_names())
    assert set(inspector.get_table_names(schema="control")) == {
        "alembic_version",
        "dataset_name_reservations",
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


def test_postgres_0002_normalizes_and_reserves_populated_dataset_names(dataset_postgres_url: str) -> None:
    engine = create_engine(dataset_postgres_url)
    _reset_to_0001(engine)
    repo_id = uuid.uuid4().hex
    dataset_id = uuid.uuid4().hex
    operation_id = uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(
            insert(repos).values(repo_id=repo_id, name="Vision", name_key="vision", namespace=f"r_{repo_id[:12]}")
        )
        connection.execute(
            insert(operations).values(
                operation_id=operation_id,
                repo_id=repo_id,
                dataset_id=dataset_id,
                kind="create_dataset",
                status="finalized",
                intent={},
            )
        )
        connection.execute(
            insert(datasets).values(
                dataset_id=dataset_id,
                repo_id=repo_id,
                name=" Clean ",
                name_key=" clean ",
                table_identifier=f"r_{repo_id[:12]}.d_{dataset_id[:12]}",
            )
        )

    _upgrade_revision(engine, "head")

    with engine.connect() as connection:
        stored = connection.execute(select(datasets.c.name, datasets.c.name_key)).one()
        reservation = connection.execute(
            select(dataset_name_reservations.c.name_key, dataset_name_reservations.c.target_dataset_id)
        ).one()
    assert stored == ("Clean", "clean")
    assert reservation == ("clean", dataset_id)
    engine.dispose()


def test_postgres_0002_rejects_normalized_name_collisions(dataset_postgres_url: str) -> None:
    engine = create_engine(dataset_postgres_url)
    _reset_to_0001(engine)
    repo_id = uuid.uuid4().hex
    first_id = uuid.uuid4().hex
    second_id = uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(
            insert(repos).values(repo_id=repo_id, name="Vision", name_key="vision", namespace=f"r_{repo_id[:12]}")
        )
        for dataset_id, name, name_key in (
            (first_id, " Clean ", " clean "),
            (second_id, "clean", "clean"),
        ):
            operation_id = uuid.uuid4().hex
            connection.execute(
                insert(operations).values(
                    operation_id=operation_id,
                    repo_id=repo_id,
                    dataset_id=dataset_id,
                    kind="create_dataset",
                    status="finalized",
                    intent={},
                )
            )
            connection.execute(
                insert(datasets).values(
                    dataset_id=dataset_id,
                    repo_id=repo_id,
                    name=name,
                    name_key=name_key,
                    table_identifier=f"r_{repo_id[:12]}.d_{dataset_id[:12]}",
                )
            )

    with pytest.raises(RuntimeError, match="collide"):
        _upgrade_revision(engine, "head")

    with engine.begin() as connection:
        connection.execute(delete(datasets).where(datasets.c.dataset_id == second_id))
        connection.execute(delete(operations).where(operations.c.dataset_id == second_id))
    _upgrade_revision(engine, "head")
    engine.dispose()


@pytest.mark.parametrize("target_table", [asset_vectors, pending_asset_vectors])
def test_postgres_rejects_vector_field_from_another_repo(dataset_postgres_url: str, target_table) -> None:  # pyright: ignore[reportUnknownParameterType]
    engine = create_engine(dataset_postgres_url)
    upgrade_control_database(engine)
    repo_a = uuid.uuid4().hex
    repo_b = uuid.uuid4().hex
    field_id = uuid.uuid4().hex
    operation_id = uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(
            insert(repos),
            [
                {"repo_id": repo_a, "name": repo_a, "name_key": repo_a, "namespace": f"r_{repo_a[:12]}"},
                {"repo_id": repo_b, "name": repo_b, "name_key": repo_b, "namespace": f"r_{repo_b[:12]}"},
            ],
        )
        connection.execute(
            insert(vector_fields).values(
                vector_field_id=field_id,
                repo_id=repo_a,
                name="embedding",
                name_key="embedding",
                dimension=2,
                numeric_type="float32",
                distance="cosine",
            )
        )
        values = {
            "repo_id": repo_b,
            "vector_field_id": field_id,
            "asset_id": "sha256:" + "1" * 64,
            "value": [1.0, 2.0],
        }
        if target_table is pending_asset_vectors:
            connection.execute(
                insert(operations).values(
                    operation_id=operation_id,
                    repo_id=repo_b,
                    kind="commit",
                    status="active",
                    intent={},
                )
            )
            values["operation_id"] = operation_id

        with pytest.raises(IntegrityError):
            with connection.begin_nested():
                connection.execute(insert(target_table).values(**values))


def test_explicit_dataset_manager_initializes_fresh_postgres_before_model_bind(dataset_postgres_url: str) -> None:
    engine = create_engine(dataset_postgres_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS vectors CASCADE"))
        connection.execute(text("DROP SCHEMA IF EXISTS control CASCADE"))

    models = ModelManager()
    manager = DatasetManager(
        control_engine=engine,
        catalog=MagicMock(),
        storage_manager=StorageManager(),
        model_manager=models,
    )

    assert inspect(engine).has_table("model_definitions", schema="control")
    manager.close()
    models.close()


def test_postgres_repo_schema_advisory_lock_is_scoped_and_reusable(dataset_postgres_url: str) -> None:
    engine_a = create_engine(dataset_postgres_url)
    engine_b = create_engine(dataset_postgres_url)
    models_a = ModelManager()
    models_b = ModelManager()
    manager_a = DatasetManager(
        control_engine=engine_a,
        catalog=MagicMock(),
        storage_manager=StorageManager(),
        model_manager=models_a,
    )
    manager_b = DatasetManager(
        control_engine=engine_b,
        catalog=MagicMock(),
        storage_manager=StorageManager(),
        model_manager=models_b,
    )
    first_acquired = threading.Event()
    release_first = threading.Event()
    same_repo_acquired = threading.Event()

    def hold_repo() -> None:
        with manager_a._repo_schema_lock(repo_id="repo-a"):  # pyright: ignore[reportPrivateUsage]
            first_acquired.set()
            release_first.wait(timeout=10)

    def wait_same_repo() -> None:
        with manager_b._repo_schema_lock(repo_id="repo-a"):  # pyright: ignore[reportPrivateUsage]
            same_repo_acquired.set()

    holder = threading.Thread(target=hold_repo)
    waiter = threading.Thread(target=wait_same_repo)
    holder.start()
    assert first_acquired.wait(timeout=10)
    waiter.start()
    assert not same_repo_acquired.wait(timeout=0.3)
    with manager_b._repo_schema_lock(repo_id="repo-b"):  # pyright: ignore[reportPrivateUsage]
        pass
    release_first.set()
    assert same_repo_acquired.wait(timeout=10)
    holder.join(timeout=10)
    waiter.join(timeout=10)
    assert not holder.is_alive()
    assert not waiter.is_alive()

    with pytest.raises(RuntimeError, match="injected"):
        with manager_a._repo_schema_lock(repo_id="repo-a"):  # pyright: ignore[reportPrivateUsage]
            raise RuntimeError("injected")
    with manager_b._repo_schema_lock(repo_id="repo-a"):  # pyright: ignore[reportPrivateUsage]
        pass

    manager_a.close()
    manager_b.close()
    models_a.close()
    models_b.close()
    engine_a.dispose()
    engine_b.dispose()
