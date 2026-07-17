"""可供多个领域复用的独立存储管理包。

MVP 不提供 Prefix alias/解绑/删除、在线凭证轮换、多个 locator fallback、Asset
Registry、外部引用验证缓存、托管对象删除或 GC。
"""

from image_gallery.storage_manager.errors import (
    ContentIntegrityError,
    ObjectAlreadyExistsError,
    ObjectNotFoundError,
    PathSecurityError,
    PrefixNotFoundError,
    StorageManagerError,
)
from image_gallery.storage_manager.manager import StorageManager
from image_gallery.storage_manager.models import StoragePrefix, StoredObject

__all__ = [
    "ContentIntegrityError",
    "ObjectAlreadyExistsError",
    "ObjectNotFoundError",
    "PathSecurityError",
    "PrefixNotFoundError",
    "StorageManager",
    "StorageManagerError",
    "StoragePrefix",
    "StoredObject",
]
