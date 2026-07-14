from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from minio import Minio
from minio.commonconfig import CopySource

from image_gallery.storage.base import Storage
from image_gallery.storage.errors import ObjectAlreadyExistsError, ObjectNotFoundError, StorageConnectionError


@dataclass
class MinioStorage(Storage):
    """MinIO storage，连接后复用 SDK client 执行对象读写。"""

    storage_name: str
    client: Any | None = field(default=None, init=False)
    bucket: str | None = field(default=None, init=False)

    def connect(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ) -> MinioStorage:
        """连接 MinIO bucket，并验证目标 bucket 已存在。"""
        self._require_text(endpoint, "endpoint")
        self._require_text(access_key, "access_key")
        self._require_text(secret_key, "secret_key")
        self._require_text(bucket, "bucket")
        try:
            client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)  # pyright: ignore[reportCallIssue]
            if not client.bucket_exists(bucket):
                raise StorageConnectionError(f"bucket does not exist: {bucket}")
        except StorageConnectionError:
            raise
        except Exception as exc:
            raise StorageConnectionError(f"minio connection failed: {endpoint}") from exc

        self.client = client
        self.bucket = bucket
        return self

    def _write_bytes(self, object_path: str, data: bytes, overwrite: bool = False) -> str:
        """写入 MinIO 对象并返回 s3:// image_uri。"""
        client, bucket = self._require_connected()
        if self.exists(object_path) and not overwrite:
            raise ObjectAlreadyExistsError(f"object already exists: {object_path}")
        client.put_object(bucket, object_path, BytesIO(data), length=len(data))
        return self.make_image_uri(object_path)

    def _read_bytes(self, object_path: str) -> bytes:
        """读取 MinIO 对象 bytes，并把对象不存在错误翻译为 ObjectNotFoundError。"""
        client, bucket = self._require_connected()
        response = None
        try:
            response = client.get_object(bucket, object_path)
            data: bytes = response.read()
            return data
        except Exception as exc:
            if self._is_not_found_error(exc):
                raise ObjectNotFoundError(f"object not found: {object_path}") from exc
            raise
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def exists(self, object_path: str) -> bool:
        """通过 stat_object 检查 MinIO 对象是否存在。"""
        client, bucket = self._require_connected()
        try:
            client.stat_object(bucket, object_path)
            return True
        except Exception as exc:
            if self._is_not_found_error(exc):
                return False
            raise

    def delete(self, object_path: str) -> None:
        """删除 MinIO 对象，不存在时抛出 ObjectNotFoundError。"""
        client, bucket = self._require_connected()
        try:
            client.remove_object(bucket, object_path)
        except Exception as exc:
            if self._is_not_found_error(exc):
                raise ObjectNotFoundError(f"object not found: {object_path}") from exc
            raise

    def copy(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
        """在同一 bucket 内复制对象并返回目标 s3:// image_uri。"""
        client, bucket = self._require_connected()
        if not self.exists(src_object_path):
            raise ObjectNotFoundError(f"object not found: {src_object_path}")
        if self.exists(dst_object_path) and not overwrite:
            raise ObjectAlreadyExistsError(f"object already exists: {dst_object_path}")
        client.copy_object(bucket, dst_object_path, CopySource(bucket, src_object_path))
        return self.make_image_uri(dst_object_path)

    def move(self, src_object_path: str, dst_object_path: str, overwrite: bool = False) -> str:
        """在同一 bucket 内移动对象并返回目标 s3:// image_uri。"""
        image_uri = self.copy(src_object_path, dst_object_path, overwrite)
        self.delete(src_object_path)
        return image_uri

    def make_image_uri(self, object_path: str) -> str:
        """把 object_path 转换为数据集可持久化的 s3:// image_uri。"""
        _, bucket = self._require_connected()
        return f"s3://{bucket}/{object_path}"

    def _require_connected(self) -> tuple[Any, str]:
        """返回已连接的 MinIO client 和 bucket。"""
        if self.client is None or self.bucket is None:
            raise StorageConnectionError(f"storage is not connected: {self.storage_name}")
        return self.client, self.bucket

    @staticmethod
    def _require_text(value: str, key: str) -> None:
        """校验 MinIO 连接参数非空。"""
        if not value:
            raise StorageConnectionError(f"minio connection requires {key}")

    @staticmethod
    def _is_not_found_error(exc: Exception) -> bool:
        """识别 MinIO SDK 返回的对象或 bucket 不存在错误。"""
        return getattr(exc, "code", None) in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}
