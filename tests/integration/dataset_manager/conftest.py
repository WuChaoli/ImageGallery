from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url
from testcontainers.minio import MinioContainer
from testcontainers.postgres import PostgresContainer


@pytest.fixture(scope="session")
def dataset_postgres_url() -> Iterator[str]:
    """启动带 pgvector 的真实 PostgreSQL Backend。"""
    with PostgresContainer("pgvector/pgvector:pg16", driver="psycopg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def dataset_minio_config() -> Iterator[dict[str, str]]:
    """启动供 S3-compatible Prefix 使用的隔离 MinIO。"""
    with MinioContainer() as minio:
        config = minio.get_config()
        client = minio.get_client()
        client.make_bucket("dataset-manager-tests")
        yield {
            "endpoint_url": f"http://{config['endpoint']}",
            "key": str(config["access_key"]),
            "secret": str(config["secret_key"]),
            "bucket": "dataset-manager-tests",
        }


@pytest.fixture
def dataset_warehouse(tmp_path: Path) -> str:
    """返回每个测试独立的 Iceberg warehouse。"""
    warehouse = tmp_path / "warehouse"
    warehouse.mkdir()
    return warehouse.as_uri()


@pytest.fixture
def dataset_catalog_url(dataset_postgres_url: str) -> str:
    """把 PyIceberg SqlCatalog 内部表隔离到 iceberg_catalog schema。"""
    url = make_url(dataset_postgres_url).update_query_dict({"options": "-csearch_path=iceberg_catalog"})
    return url.render_as_string(hide_password=False)
