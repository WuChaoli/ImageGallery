from pathlib import Path
from urllib.parse import unquote, urlparse

from image_gallery.storage.errors import InvalidStorageUriError, UnsafeStoragePathError


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


def _is_windows_drive_scheme(scheme: str) -> bool:
    """判断 urlparse 解析出的 scheme 是否为 Windows 盘符（如 'c'）。"""
    return len(scheme) == 1 and scheme.isalpha()


def file_image_uri_to_path(image_uri: str) -> Path:
    """把本地绝对路径或 file URI 规范化为 Path。"""
    parsed = urlparse(image_uri)
    if parsed.scheme == "" or _is_windows_drive_scheme(parsed.scheme):
        # 无 scheme 或单字母 scheme（Windows 盘符如 C:\...）均视为本地路径
        path = Path(image_uri)
    elif parsed.scheme == "file":
        raw_path = unquote(parsed.path)
        # Windows file URI: file:///C:/... -> 去掉前导 /
        if len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
            raw_path = raw_path[1:]
        path = Path(raw_path)
    else:
        raise InvalidStorageUriError(f"unsupported file image_uri scheme: {parsed.scheme}")
    if not path.is_absolute():
        raise InvalidStorageUriError(f"image_uri must be an absolute path or file URI: {image_uri}")
    return path.expanduser().resolve()


def is_file_image_uri_under_root(root: str | Path, image_uri: str) -> bool:
    """判断本地 image_uri 是否属于指定 storage root。"""
    try:
        root_path = Path(root).expanduser().resolve()
        resolved = file_image_uri_to_path(image_uri)
    except InvalidStorageUriError:
        return False
    return root_path == resolved or root_path in resolved.parents


def require_file_image_uri_under_root(root: str | Path, image_uri: str) -> Path:
    """校验本地 image_uri 属于受管 storage root，并返回规范化路径。"""
    resolved = file_image_uri_to_path(image_uri)
    root_path = Path(root).expanduser().resolve()
    if root_path != resolved and root_path not in resolved.parents:
        raise UnsafeStoragePathError(f"image_uri is outside storage root: {image_uri}")
    return resolved
