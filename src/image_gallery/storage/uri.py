from pathlib import Path

from image_gallery.storage.errors import UnsafeStoragePathError


def resolve_object_path(root: str | Path, object_path: str) -> Path:
    """把 object_path 安全解析到 storage root 下。"""
    if not object_path or object_path.strip() == "":
        raise UnsafeStoragePathError("object_path must not be empty")

    candidate = Path(object_path)
    if candidate.is_absolute():
        raise UnsafeStoragePathError(f"absolute object_path is not allowed: {object_path}")

    root_path = Path(root).expanduser().resolve()
    resolved = (root_path / candidate).resolve()
    if root_path != resolved and root_path not in resolved.parents:
        raise UnsafeStoragePathError(f"object_path escapes storage root: {object_path}")
    return resolved


def make_file_image_uri(root: str | Path, object_path: str) -> str:
    """生成当前环境可直接读取的本地 image_uri。"""
    return str(resolve_object_path(root, object_path))
