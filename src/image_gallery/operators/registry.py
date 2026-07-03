from image_gallery.cleaning.errors import UnknownOperatorError
from image_gallery.operators.backends.base import BackendAdapter
from image_gallery.operators.spec import OperatorSpec


class OperatorRegistry:
    """逻辑算子和后端 adapter 注册表。"""

    def __init__(self) -> None:
        self._operators: dict[str, OperatorSpec] = {}
        self._backends: dict[str, BackendAdapter] = {}

    def register_operator(self, spec: OperatorSpec) -> None:
        """注册逻辑算子。"""
        self._operators[spec.name] = spec

    def register_backend(self, backend: BackendAdapter) -> None:
        """注册物理后端。"""
        self._backends[backend.name] = backend

    def get_operator(self, operator_name: str) -> OperatorSpec:
        """按名称获取逻辑算子。"""
        try:
            return self._operators[operator_name]
        except KeyError as exc:
            raise UnknownOperatorError(f"unknown operator: {operator_name}") from exc

    def get_backend(self, backend_name: str) -> BackendAdapter:
        """按名称获取后端 adapter。"""
        try:
            return self._backends[backend_name]
        except KeyError as exc:
            raise UnknownOperatorError(f"unknown backend: {backend_name}") from exc

    def list_operators(self) -> list[str]:
        """返回当前可用算子名称。"""
        return sorted(self._operators)

    def resolve(self, operator_name: str) -> tuple[OperatorSpec, BackendAdapter]:
        """返回算子及其唯一后端。"""
        spec = self.get_operator(operator_name)
        return spec, self.get_backend(spec.backend_name)
