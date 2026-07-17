import faulthandler
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url
from testcontainers.minio import MinioContainer
from testcontainers.postgres import PostgresContainer

LOGGER = logging.getLogger(__name__)
_DATASET_BACKEND_TIMEOUT_SECONDS = 360


@pytest.fixture(scope="session", autouse=True)
def dataset_backend_timeout_guard() -> Iterator[None]:
    """真实后端测试阻塞时输出全部线程堆栈并终止进程。"""
    faulthandler.dump_traceback_later(_DATASET_BACKEND_TIMEOUT_SECONDS, repeat=False, exit=True)
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()


@pytest.fixture(scope="session")
def dataset_postgres_url() -> Iterator[str]:
    """启动带 pgvector 的真实 PostgreSQL Backend。"""
    LOGGER.info("dataset-backend-fixture stage=postgres status=start")
    with PostgresContainer("pgvector/pgvector:pg16", driver="psycopg") as postgres:
        LOGGER.info("dataset-backend-fixture stage=postgres status=ready")
        url = make_url(postgres.get_connection_url())
        if url.host == "localhost":
            url = url.set(host="127.0.0.1")
        yield url.update_query_dict({"connect_timeout": "15"}).render_as_string(hide_password=False)
    LOGGER.info("dataset-backend-fixture stage=postgres status=closed")


@pytest.fixture(scope="session")
def dataset_minio_config() -> Iterator[dict[str, str]]:
    """启动供 S3-compatible Prefix 使用的隔离 MinIO。"""
    LOGGER.info("dataset-backend-fixture stage=minio status=start")
    with MinioContainer() as minio:
        config = minio.get_config()
        client = minio.get_client()
        client.make_bucket("dataset-manager-tests")
        LOGGER.info("dataset-backend-fixture stage=minio status=ready")
        yield {
            "endpoint_url": f"http://{config['endpoint']}",
            "key": str(config["access_key"]),
            "secret": str(config["secret_key"]),
            "bucket": "dataset-manager-tests",
        }
    LOGGER.info("dataset-backend-fixture stage=minio status=closed")


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
