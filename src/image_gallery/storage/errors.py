class StorageError(Exception):
    """Storage 模块基础异常。"""


class InvalidStorageUriError(StorageError):
    """image_uri 或 storage URI 无法被当前配置解析。"""


class StorageNotFoundError(StorageError):
    """请求的 storage_name 未注册。"""


class UnsupportedStorageTypeError(StorageError):
    """storage type 当前版本不支持。"""


class StorageConnectionError(StorageError):
    """Storage 未连接或连接校验失败。"""


class UnsafeStoragePathError(StorageError):
    """object_path 试图逃逸受管 storage root。"""


class ObjectAlreadyExistsError(StorageError):
    """默认不允许覆盖已存在对象。"""


class ObjectNotFoundError(StorageError):
    """读取、复制、移动或删除的对象不存在。"""
