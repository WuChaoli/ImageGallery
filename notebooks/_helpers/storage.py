"""MinIO initialization helpers for notebook validation flows."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from image_gallery.storage import MinioStorage
from notebooks._helpers.paths import get_repo_root


def read_required_env(name: str) -> str:
    """Read one required environment variable and return a stripped value."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def load_minio_storage() -> MinioStorage:
    """Load MinIO settings from .env and return a connected storage instance."""
    for env_path in _env_path_candidates():
        if env_path.exists():
            load_dotenv(env_path)
            break

    endpoint = read_required_env("IMAGE_GALLERY_MINIO_ENDPOINT")
    access_key = read_required_env("IMAGE_GALLERY_MINIO_ACCESS_KEY")
    secret_key = read_required_env("IMAGE_GALLERY_MINIO_SECRET_KEY")
    bucket = read_required_env("IMAGE_GALLERY_MINIO_BUCKET")

    parsed = urlparse(endpoint)
    connect_endpoint = parsed.netloc or endpoint
    secure = parsed.scheme == "https"

    return MinioStorage(storage_name="notebook_validation_minio").connect(
        endpoint=connect_endpoint,
        access_key=access_key,
        secret_key=secret_key,
        bucket=bucket,
        secure=secure,
    )


def _env_path_candidates() -> list[Path]:
    """Return .env candidates for normal checkouts and linked worktrees."""
    repo_root = get_repo_root()
    candidates = [repo_root / ".env"]
    if repo_root.parent.name == ".worktrees":
        candidates.append(repo_root.parent.parent / ".env")
    return candidates
