"""DatasetManager Notebook 的材料、环境和生命周期辅助函数。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

from dotenv import dotenv_values
from PIL import Image
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from image_gallery.dataset_manager import Dataset, DatasetManager, DatasetView
from image_gallery.importers import SourceParser
from image_gallery.model_manager import ModelDefinition, ModelManager
from image_gallery.storage_manager import StorageManager

REQUIRED_ENV_FIELDS = (
    "IMAGE_GALLERY_DEMO_POSTGRES_URL",
    "IMAGE_GALLERY_DEMO_CATALOG_URL",
    "IMAGE_GALLERY_DEMO_WAREHOUSE",
    "IMAGE_GALLERY_DEMO_MINIO_ENDPOINT",
    "IMAGE_GALLERY_DEMO_MINIO_ACCESS_KEY",
    "IMAGE_GALLERY_DEMO_MINIO_SECRET_KEY",
    "IMAGE_GALLERY_DEMO_MINIO_BUCKET",
)
DEMO_RESOURCE_LABEL = "com.image-gallery.dataset-manager-demo"


class DemoEmbeddingRuntime:
    """为离线 Notebook 提供确定性二维 embedding。"""

    def embed(self, images: list[bytes]) -> list[tuple[float, ...]]:
        """基于图片长度返回确定性向量。"""
        return [(float(len(value)), 1.0) for value in images]

    def close(self) -> None:
        """关闭无状态演示运行时。"""


@dataclass(frozen=True)
class DemoConfigProbe:
    """描述 `.env` 配置是否足以继续连接检查。"""

    ready: bool
    values: dict[str, str]
    missing_fields: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass
class DemoBackendSession:
    """区分外部服务与由演示创建的受管服务。"""

    mode: Literal["existing", "managed"]
    config: dict[str, str]
    resources: list[object] = field(default_factory=list, repr=False)


@dataclass(frozen=True, slots=True)
class DemoImportResult:
    """描述演示导入的一次原子提交。"""

    view: DatasetView
    imported_count: int
    asset_ids: tuple[str, ...]


class DemoDatasetImporter:
    """正式 Importer 切换前，仅供 examples 使用的 DatasetManager adapter。"""

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
        self.source = source
        self.dataset = dataset
        self.base = base
        self.storage_manager = storage_manager
        self.prefix_id = prefix_id
        self.tag_ids = sorted(set(tag_ids or []))

    def run(self) -> DemoImportResult:
        """托管全部本地图片后，以精确 Branch 基线发布一次 commit。"""
        if self.base.ref_type != "branch":
            raise ValueError("base 必须是 Branch DatasetView")
        current = self.dataset.open_branch(name=self.base.ref_name)
        if current.snapshot_id != self.base.snapshot_id:
            from image_gallery.dataset_manager import ConflictError

            raise ConflictError(f"Branch {self.base.ref_name} 已变化")
        rows: list[dict[str, object]] = []
        asset_ids: list[str] = []
        for record in self.source.parse():
            if record.local_path is None:
                raise ValueError("演示导入要求 local_path")
            data = record.local_path.read_bytes()
            prefix = self.storage_manager.get_prefix(prefix_id=self.prefix_id)
            if prefix.backend == "s3":
                # 部分 MinIO 版本拒绝 s3fs mv() 的批量删除请求；演示 adapter 直接写入同一内容地址并显式校验。
                digest = hashlib.sha256(data).hexdigest()
                relative_path = f"demo/sha256/{digest[:2]}/{digest}"
                self.storage_manager.write_bytes(
                    prefix_id=self.prefix_id,
                    relative_path=relative_path,
                    data=data,
                    overwrite=True,
                )
                stored = self.storage_manager.verify_external(
                    prefix_id=self.prefix_id,
                    relative_path=relative_path,
                )
            else:
                stored = self.storage_manager.write_managed(prefix_id=self.prefix_id, data=data)
            asset_ids.append(stored.asset_id)
            rows.append(
                {
                    "asset_id": stored.asset_id,
                    "storage_prefix_id": stored.storage_prefix_id,
                    "relative_path": stored.relative_path,
                    "source_uri": record.source_uri,
                    "tag_ids": self.tag_ids,
                }
            )
        result = self.dataset.commit(branch=self.base.ref_name, base=self.base, frame=pd.DataFrame(rows))
        return DemoImportResult(result.view, len(rows), tuple(asset_ids))


def validate_sample_manifest(manifest_path: str | Path) -> list[dict[str, object]]:
    """校验 20 张演示图片的来源、数量、可解码性和内容哈希。"""
    path = Path(manifest_path)
    payload = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    if payload.get("seed") != 20260717 or payload.get("source_row_count") != 1000:
        raise ValueError("manifest 抽样参数不正确")
    items = cast(list[dict[str, object]], payload.get("items"))
    if payload.get("sample_size") != 20 or len(items) != 20:
        raise ValueError("manifest 必须描述 20 张图片")
    hashes: set[str] = set()
    local_paths: set[str] = set()
    for item in items:
        required = {"source_image_uri", "local_path", "sha256", "size_bytes"}
        if not required.issubset(item):
            raise ValueError("manifest 条目缺少必需字段")
        relative_path = str(item["local_path"])
        image_path = path.parent / relative_path
        if not image_path.is_file():
            raise ValueError(f"演示图片不存在: {relative_path}")
        data = image_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != item["sha256"] or len(data) != item["size_bytes"]:
            raise ValueError(f"演示图片内容校验失败: {relative_path}")
        with Image.open(image_path) as image:
            image.verify()
        if digest in hashes or relative_path in local_paths:
            raise ValueError("演示图片存在重复条目")
        hashes.add(digest)
        local_paths.add(relative_path)
    return items


def load_demo_config(env_path: str | Path) -> DemoConfigProbe:
    """只读加载演示配置；该函数不会创建容器或改写环境文件。"""
    path = Path(env_path)
    if not path.is_file():
        return DemoConfigProbe(False, {}, REQUIRED_ENV_FIELDS, (f"未找到配置文件: {path}",))
    raw = dotenv_values(path)
    values = {name: str(value).strip() for name, value in raw.items() if value is not None and str(value).strip()}
    missing = tuple(name for name in REQUIRED_ENV_FIELDS if name not in values)
    diagnostics = tuple(f"缺少配置项: {name}" for name in missing)
    return DemoConfigProbe(not missing, values, missing, diagnostics)


def probe_existing_backend(
    env_path: str | Path,
    *,
    checks: tuple[Callable[[dict[str, str]], str | None], ...] | None = None,
) -> DemoConfigProbe:
    """探测已有 Backend；任何失败都返回诊断而不自动创建替代环境。"""
    config = load_demo_config(env_path)
    if not config.ready:
        return config
    selected_checks = checks or (_check_postgres, _check_warehouse, _check_minio)
    diagnostics = tuple(message for check in selected_checks if (message := check(config.values)) is not None)
    return DemoConfigProbe(not diagnostics, config.values, (), diagnostics)


def require_ready_backend(probe: DemoConfigProbe) -> dict[str, str]:
    """在环境未通过探测时阻止 Notebook 进入业务旅程。"""
    if not probe.ready:
        raise RuntimeError("Backend 尚未就绪，请修复 .env 或显式创建 demo Backend")
    return probe.values


def _check_postgres(values: dict[str, str]) -> str | None:
    """检查 PostgreSQL 连接与 pgvector extension。"""
    engine = create_engine(values["IMAGE_GALLERY_DEMO_POSTGRES_URL"], connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as connection:
            available = connection.execute(text("SELECT 1 FROM pg_available_extensions WHERE name='vector'")).first()
            if available is None:
                return "PostgreSQL 未提供 pgvector extension"
    except Exception as exc:  # noqa: BLE001 - 演示探测边界需要把驱动异常转为安全诊断。
        return f"PostgreSQL 不可连接: {type(exc).__name__}"
    finally:
        engine.dispose()
    return None


def _check_warehouse(values: dict[str, str]) -> str | None:
    """检查 file warehouse 可写性；对象存储 warehouse 交给 Catalog 初始化验证。"""
    warehouse = values["IMAGE_GALLERY_DEMO_WAREHOUSE"]
    if warehouse.startswith("file://"):
        path = Path(warehouse.removeprefix("file:///"))
        if not path.parent.exists():
            return "PyIceberg Warehouse 父目录不存在"
    return None


def _check_minio(values: dict[str, str]) -> str | None:
    """检查 MinIO endpoint、凭证和 bucket。"""
    from urllib.parse import urlparse

    from minio import Minio

    parsed = urlparse(values["IMAGE_GALLERY_DEMO_MINIO_ENDPOINT"])
    try:
        client = Minio(
            parsed.netloc or parsed.path,
            access_key=values["IMAGE_GALLERY_DEMO_MINIO_ACCESS_KEY"],
            secret_key=values["IMAGE_GALLERY_DEMO_MINIO_SECRET_KEY"],
            secure=parsed.scheme == "https",
        )
        if not client.bucket_exists(values["IMAGE_GALLERY_DEMO_MINIO_BUCKET"]):
            return "MinIO bucket 不存在"
    except Exception as exc:  # noqa: BLE001 - 演示探测边界需要把 SDK 异常转为安全诊断。
        return f"MinIO 不可连接: {type(exc).__name__}"
    return None


def stop_demo_backend(session: DemoBackendSession, *, remove_volumes: bool = False) -> None:
    """停止受管 demo 资源；拒绝对 existing session 执行破坏性操作。"""
    if session.mode != "managed":
        raise ValueError("existing session 不允许停止容器或删除 volume")
    for resource in reversed(session.resources):
        labels = getattr(resource, "_kwargs", {}).get("labels", {})
        if labels.get(DEMO_RESOURCE_LABEL) != "managed":
            raise ValueError("拒绝停止没有 DatasetManager demo label 的资源")
        stop = getattr(resource, "stop", None)
        if callable(stop):
            stop()
    session.resources.clear()


def start_demo_backend(*, demo_root: str | Path, recreate: bool = False) -> DemoBackendSession:
    """显式启动真实 PostgreSQL/pgvector 与 MinIO 演示服务。"""
    from minio import Minio
    from testcontainers.minio import MinioContainer
    from testcontainers.postgres import PostgresContainer

    root = Path(demo_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    postgres = PostgresContainer("pgvector/pgvector:pg16", driver="psycopg").with_kwargs(
        labels={DEMO_RESOURCE_LABEL: "managed"}
    )
    minio = MinioContainer().with_kwargs(labels={DEMO_RESOURCE_LABEL: "managed"})
    resources: list[object] = []
    try:
        postgres.start()
        resources.append(postgres)
        minio.start()
        resources.append(minio)
        url = make_url(postgres.get_connection_url())
        if url.host == "localhost":
            url = url.set(host="127.0.0.1")
        postgres_url = url.update_query_dict({"connect_timeout": "15"}).render_as_string(hide_password=False)
        catalog_url = (
            make_url(postgres_url)
            .update_query_dict({"connect_timeout": "15", "options": "-csearch_path=iceberg_catalog"})
            .render_as_string(hide_password=False)
        )
        minio_config = minio.get_config()
        bucket = "image-gallery-demo"
        client = Minio(
            str(minio_config["endpoint"]),
            access_key=str(minio_config["access_key"]),
            secret_key=str(minio_config["secret_key"]),
            secure=False,
        )
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
        values = {
            "IMAGE_GALLERY_DEMO_POSTGRES_URL": postgres_url,
            "IMAGE_GALLERY_DEMO_CATALOG_URL": catalog_url,
            "IMAGE_GALLERY_DEMO_WAREHOUSE": (root / "warehouse").as_uri(),
            "IMAGE_GALLERY_DEMO_MINIO_ENDPOINT": f"http://{minio_config['endpoint']}",
            "IMAGE_GALLERY_DEMO_MINIO_ACCESS_KEY": str(minio_config["access_key"]),
            "IMAGE_GALLERY_DEMO_MINIO_SECRET_KEY": str(minio_config["secret_key"]),
            "IMAGE_GALLERY_DEMO_MINIO_BUCKET": bucket,
        }
        (root / ".env.demo").write_text(
            "\n".join(f"{key}={value}" for key, value in values.items()) + "\n", encoding="utf-8"
        )
        return DemoBackendSession("managed", values, resources)
    except Exception as exc:
        for resource in reversed(resources):
            resource.stop()
        raise RuntimeError(f"无法启动 demo Backend: {type(exc).__name__}") from exc


def open_demo_clients(config: dict[str, str]) -> tuple[StorageManager, DatasetManager, str]:
    """按统一配置创建 StorageManager、DatasetManager 和稳定 S3 Prefix。"""
    credentials = {
        "key": config["IMAGE_GALLERY_DEMO_MINIO_ACCESS_KEY"],
        "secret": config["IMAGE_GALLERY_DEMO_MINIO_SECRET_KEY"],
    }
    storage = StorageManager(credential_provider=lambda _ref: credentials)
    models = ModelManager(providers={"demo": lambda _definition, _secrets: DemoEmbeddingRuntime()})
    models.register(
        ModelDefinition(
            model_id="demo-image-length-v1",
            provider="demo",
            artifact_uri="builtin://demo-image-length",
            artifact_revision="v1",
            artifact_checksum="sha256:" + "1" * 64,
            dimension=2,
            dtype="float32",
            config={},
        )
    )
    bucket = config["IMAGE_GALLERY_DEMO_MINIO_BUCKET"]
    prefix = storage.register_s3_prefix(
        name="demo-images",
        root=f"{bucket}/dataset-manager-demo",
        endpoint_url=config["IMAGE_GALLERY_DEMO_MINIO_ENDPOINT"],
        credential_ref="demo-minio",
        prefix_id="dataset-manager-demo-images",
    )
    manager = DatasetManager.postgres(
        control_url=config["IMAGE_GALLERY_DEMO_POSTGRES_URL"],
        catalog_url=config["IMAGE_GALLERY_DEMO_CATALOG_URL"],
        warehouse=config["IMAGE_GALLERY_DEMO_WAREHOUSE"],
        storage_manager=storage,
        model_manager=models,
    )
    return storage, manager, prefix.prefix_id
