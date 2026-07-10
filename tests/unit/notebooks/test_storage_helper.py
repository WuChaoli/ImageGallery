from __future__ import annotations

from pathlib import Path

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


def test_load_minio_storage_falls_back_to_main_checkout_env(
    tmp_path: Path,
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

    for name in [
        "IMAGE_GALLERY_MINIO_ENDPOINT",
        "IMAGE_GALLERY_MINIO_ACCESS_KEY",
        "IMAGE_GALLERY_MINIO_SECRET_KEY",
        "IMAGE_GALLERY_MINIO_BUCKET",
    ]:
        monkeypatch.delenv(name, raising=False)
    main_root = tmp_path / "ImageGallery"
    worktree_root = main_root / ".worktrees" / "feature"
    worktree_root.mkdir(parents=True)
    (worktree_root / "pyproject.toml").write_text("[project]\nname = \"image-gallery\"\n", encoding="utf-8")
    (main_root / ".env").write_text(
        "\n".join(
            [
                "IMAGE_GALLERY_MINIO_ENDPOINT=http://127.0.0.1:9000",
                "IMAGE_GALLERY_MINIO_ACCESS_KEY=access-key",
                "IMAGE_GALLERY_MINIO_SECRET_KEY=secret-key",
                "IMAGE_GALLERY_MINIO_BUCKET=bucket-a",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(worktree_root)
    monkeypatch.setattr(MinioStorage, "connect", fake_connect)

    storage = load_minio_storage()

    assert storage.bucket == "bucket-a"
    assert observed["endpoint"] == "127.0.0.1:9000"
