"""StorageManager 稳定领域错误。"""


class StorageManagerError(Exception):
    """表示 StorageManager 操作失败。"""


class PathSecurityError(StorageManagerError, ValueError):
    """表示路径不安全或逃逸 Prefix root。"""


class ObjectAlreadyExistsError(StorageManagerError, FileExistsError):
    """表示对象存在且调用方未允许覆盖。"""


class ObjectNotFoundError(StorageManagerError, FileNotFoundError):
    """表示目标对象不存在。"""


class ContentIntegrityError(StorageManagerError, ValueError):
    """表示实际 bytes 与预期内容身份不一致。"""


class PrefixNotFoundError(StorageManagerError, KeyError):
    """表示 Storage Prefix 不存在。"""
