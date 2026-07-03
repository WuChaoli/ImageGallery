class CleaningError(Exception):
    """清洗模块基础错误。"""


class OperatorConfigError(CleaningError):
    """算子配置格式错误。"""


class UnknownOperatorError(CleaningError):
    """请求了未注册的 operator_name。"""


class CleanerStateError(CleaningError):
    """Cleaner 当前状态不支持该操作。"""


class BackendExecutionError(CleaningError):
    """后端执行失败。"""
