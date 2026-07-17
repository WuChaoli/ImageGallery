"""ModelManager 稳定领域错误。"""


class ModelManagerError(Exception):
    """表示模型管理操作失败。"""


class ModelRegistrationError(ModelManagerError, ValueError):
    """表示稳定模型身份与冻结定义冲突。"""


class ModelRuntimeError(ModelManagerError, RuntimeError):
    """表示模型运行时不可用或输出不满足契约。"""
