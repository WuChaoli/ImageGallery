"""DatasetManager 稳定领域错误。"""


class DatasetManagerError(Exception):
    """表示新数据集平台操作失败。"""


class NameConflictError(DatasetManagerError, ValueError):
    """表示名称在所属作用域内冲突。"""


class ObjectNotFoundError(DatasetManagerError, LookupError):
    """表示 Repo 或 Dataset 不存在。"""


class StorageAuthorizationError(DatasetManagerError, PermissionError):
    """表示 DatasetRepo 未授权使用 Storage Prefix。"""


class ConflictError(DatasetManagerError):
    """表示目标 Branch 已偏离调用方的精确基线。"""


class ValidationError(DatasetManagerError, ValueError):
    """表示提交数据不满足 Dataset 契约。"""
