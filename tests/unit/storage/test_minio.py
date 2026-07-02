from __future__ import annotations

from dataclasses import dataclass
from inspect import Parameter, signature

import pytest

from image_gallery.storage.errors import ObjectAlreadyExistsError, ObjectNotFoundError, StorageConnectionError
from image_gallery.storage.minio import MinioStorage


class FakeObjectMissingError(Exception):
    """模拟 MinIO SDK 中表示对象不存在的异常。"""

    code = "NoSuchKey"


@dataclass
class FakeResponse:
    """模拟 MinIO get_object 返回的响应对象。"""

    data: bytes
    closed: bool = False
    released: bool = False

    def read(self) -> bytes:
        return self.data

    def close(self) -> None:
        self.closed = True

    def release_conn(self) -> None:
        self.released = True


class FakeMinioClient:
    """内存版 MinIO client，用于验证 Storage 与 SDK 的交互契约。"""

    instances: list[FakeMinioClient] = []
    bucket_available = True

    def __init__(self, endpoint: str, access_key: str, secret_key: str, secure: bool) -> None:
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self.objects: dict[str, bytes] = {}
        self.last_response: FakeResponse | None = None
        FakeMinioClient.instances.append(self)

    def bucket_exists(self, bucket: str) -> bool:
        self.bucket = bucket
        return self.bucket_available

    def stat_object(self, bucket: str, object_path: str) -> object:
        if object_path not in self.objects:
            raise FakeObjectMissingError()
        return object()

    def put_object(self, bucket: str, object_path: str, data: object, length: int) -> None:
        self.objects[object_path] = data.read(length)

    def get_object(self, bucket: str, object_path: str) -> FakeResponse:
        if object_path not in self.objects:
            raise FakeObjectMissingError()
        self.last_response = FakeResponse(self.objects[object_path])
        return self.last_response

    def remove_object(self, bucket: str, object_path: str) -> None:
        if object_path not in self.objects:
            raise FakeObjectMissingError()
        del self.objects[object_path]

    def copy_object(self, bucket: str, dst_object_path: str, source: object) -> None:
        src_object_path = source.object_name
        if src_object_path not in self.objects:
            raise FakeObjectMissingError()
        self.objects[dst_object_path] = self.objects[src_object_path]


@pytest.fixture(autouse=True)
def reset_fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeMinioClient.instances = []
    FakeMinioClient.bucket_available = True
    monkeypatch.setattr("image_gallery.storage.minio.Minio", FakeMinioClient)


def test_minio_connect_exposes_explicit_connection_parameters() -> None:
    parameters = signature(MinioStorage.connect).parameters

    assert list(parameters) == ["self", "endpoint", "access_key", "secret_key", "bucket", "secure"]
    assert parameters["secure"].default is False
    assert all(parameter.kind is not Parameter.VAR_KEYWORD for parameter in parameters.values())


def test_minio_storage_connects_and_checks_bucket() -> None:
    storage = MinioStorage(storage_name="minio_main").connect(
        endpoint="127.0.0.1:9000",
        access_key="admin",
        secret_key="YourStrongPassword123",
        bucket="images",
        secure=False,
    )

    client = FakeMinioClient.instances[0]
    assert storage.client is client
    assert storage.bucket == "images"
    assert client.endpoint == "127.0.0.1:9000"
    assert client.access_key == "admin"
    assert client.secret_key == "YourStrongPassword123"
    assert client.secure is False


def test_minio_storage_rejects_missing_bucket() -> None:
    FakeMinioClient.bucket_available = False

    with pytest.raises(StorageConnectionError, match="bucket does not exist"):
        MinioStorage(storage_name="minio_main").connect(
            endpoint="127.0.0.1:9000",
            access_key="admin",
            secret_key="secret",
            bucket="missing",
            secure=False,
        )


def test_minio_storage_writes_reads_and_closes_response() -> None:
    storage = MinioStorage(storage_name="minio_main").connect(
        endpoint="127.0.0.1:9000",
        access_key="admin",
        secret_key="secret",
        bucket="images",
        secure=False,
    )

    image_uri = storage.write_bytes("images/a.jpg", b"abc")
    data = storage.read_bytes("images/a.jpg")

    assert image_uri == "s3://images/images/a.jpg"
    assert data == b"abc"
    assert storage.exists("images/a.jpg") is True
    assert FakeMinioClient.instances[0].last_response is not None
    assert FakeMinioClient.instances[0].last_response.closed is True
    assert FakeMinioClient.instances[0].last_response.released is True


def test_minio_storage_preserves_overwrite_and_missing_object_errors() -> None:
    storage = MinioStorage(storage_name="minio_main").connect(
        endpoint="127.0.0.1:9000",
        access_key="admin",
        secret_key="secret",
        bucket="images",
        secure=False,
    )
    storage.write_bytes("images/a.jpg", b"abc")

    with pytest.raises(ObjectAlreadyExistsError):
        storage.write_bytes("images/a.jpg", b"def")
    with pytest.raises(ObjectNotFoundError):
        storage.read_bytes("images/missing.jpg")


def test_minio_storage_copies_moves_and_deletes_objects() -> None:
    storage = MinioStorage(storage_name="minio_main").connect(
        endpoint="127.0.0.1:9000",
        access_key="admin",
        secret_key="secret",
        bucket="images",
        secure=False,
    )
    storage.write_bytes("images/a.jpg", b"abc")

    copy_uri = storage.copy("images/a.jpg", "images/b.jpg")
    move_uri = storage.move("images/b.jpg", "images/c.jpg")
    storage.delete("images/a.jpg")

    assert copy_uri == "s3://images/images/b.jpg"
    assert move_uri == "s3://images/images/c.jpg"
    assert storage.exists("images/a.jpg") is False
    assert storage.read_bytes("images/c.jpg") == b"abc"


def test_minio_storage_requires_connection_before_io() -> None:
    storage = MinioStorage(storage_name="minio_main")

    with pytest.raises(StorageConnectionError, match="storage is not connected"):
        storage.write_bytes("images/a.jpg", b"abc")
