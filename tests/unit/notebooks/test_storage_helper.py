from __future__ import annotations

import pytest
from notebooks._helpers.storage import load_minio_storage, read_required_env

from image_gallery.storage.minio import MinioStorage


def test_read_required_env_returns_stripped_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IMAGE_GALLERY_MINIO_ENDPOINT", "  http://127.0.0.1:9000  ")
    assert read_required_env("IMAGE_GALLERY_MINIO_ENDPOINT") == "http://127.0.0.1:9000"


def test_read_required_env_raises_for_missing_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("IMAGE_GALLERY_MINIO_ENDPOINT", raising=False)

    with pytest.raises(RuntimeError, match="IMAGE_GALLERY_MINIO_ENDPOINT"):
        read_required_env("IMAGE_GALLERY_MINIO_ENDPOINT")


def test_load_minio_storage_uses_env_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def fake_connect(
        self: MinioStorage,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ) -> MinioStorage:
        observed.update(
            {
                "endpoint": endpoint,
                "access_key": access_key,
                "secret_key": secret_key,
                "bucket": bucket,
                "secure": secure,
            }
        )
        self.bucket = bucket
        return self

    monkeypatch.setenv("IMAGE_GALLERY_MINIO_ENDPOINT", "https://minio.example.com")
    monkeypatch.setenv("IMAGE_GALLERY_MINIO_ACCESS_KEY", "access-key")
    monkeypatch.setenv("IMAGE_GALLERY_MINIO_SECRET_KEY", "secret-key")
    monkeypatch.setenv("IMAGE_GALLERY_MINIO_BUCKET", "bucket-a")
    monkeypatch.setattr(MinioStorage, "connect", fake_connect)

    storage = load_minio_storage()

    assert storage.bucket == "bucket-a"
    assert observed == {
        "endpoint": "minio.example.com",
        "access_key": "access-key",
        "secret_key": "secret-key",
        "bucket": "bucket-a",
        "secure": True,
    }
