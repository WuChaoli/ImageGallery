"""StorageManager 私有路径规则。"""

from __future__ import annotations

import uuid
from pathlib import Path, PurePosixPath

from image_gallery.storage_manager.errors import PathSecurityError
from image_gallery.storage_manager.models import StoragePrefix

RESERVED_ROOT = ".image-gallery"


def normalize_relative_path(relative_path: str, *, allow_reserved: bool) -> str:
    """规范化并验证 Prefix 内的 POSIX 相对路径。"""
    normalized = relative_path.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise PathSecurityError(relative_path)
    if not allow_reserved and path.parts[0] == RESERVED_ROOT:
        raise PathSecurityError(relative_path)
    return path.as_posix()


def resolve_file_path(*, prefix: StoragePrefix, relative_path: str, allow_reserved: bool) -> Path:
    """解析 file Prefix 路径并拒绝 root escape 与符号链接逃逸。"""
    if prefix.backend != "file":
        raise NotImplementedError(f"Backend is not implemented: {prefix.backend}")
    normalized = normalize_relative_path(relative_path, allow_reserved=allow_reserved)
    root = Path(prefix.root).resolve()
    candidate = root.joinpath(*PurePosixPath(normalized).parts)
    resolved = candidate.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise PathSecurityError(relative_path)
    return resolved


def object_path(*, prefix: StoragePrefix, relative_path: str) -> str:
    """拼接 S3-compatible root 与已验证相对路径。"""
    return f"{prefix.root.rstrip('/')}/{relative_path}"


def managed_relative_path(asset_id: str) -> str:
    """根据规范 SHA-256 身份返回确定性托管路径。"""
    digest = asset_id.removeprefix("sha256:")
    return f"{RESERVED_ROOT}/managed/sha256/{digest[:2]}/{digest[2:4]}/{digest}"


def staging_relative_path() -> str:
    """返回一次操作使用的随机 staging 相对路径。"""
    return f"{RESERVED_ROOT}/staging/{uuid.uuid4().hex}"
