from image_gallery.cleaning.errors import UnknownOperatorError
from image_gallery.operators.computers.base import ParameterComputer
from image_gallery.operators.spec import OperatorSpec


class OperatorRegistry:
    """逻辑算子和参数计算单元注册表。"""

    def __init__(self) -> None:
        self._operators: dict[str, OperatorSpec] = {}
        self._parameter_computers: dict[str, ParameterComputer] = {}

    def register_operator(self, spec: OperatorSpec) -> None:
        """注册逻辑算子。"""
        self._operators[spec.name] = spec

    def register_parameter_computer(self, computer: ParameterComputer) -> None:
        """注册参数计算单元。"""
        self._parameter_computers[computer.name] = computer

    def get_operator(self, operator_name: str) -> OperatorSpec:
        """按名称获取逻辑算子。"""
        try:
            return self._operators[operator_name]
        except KeyError as exc:
            raise UnknownOperatorError(f"unknown operator: {operator_name}") from exc

    def get_parameter_computer(self, computer_name: str) -> ParameterComputer:
        """按名称获取参数计算单元。"""
        try:
            return self._parameter_computers[computer_name]
        except KeyError as exc:
            raise UnknownOperatorError(f"unknown parameter computer: {computer_name}") from exc

    def list_operators(self) -> list[str]:
        """返回当前可用算子名称。"""
        return sorted(self._operators)

    def find_computers_for_parameters(self, parameter_names: set[str]) -> list[ParameterComputer]:
        """按参数需求返回可覆盖这些参数的计算单元。"""
        remaining = set(parameter_names)
        selected: list[ParameterComputer] = []
        for computer in self._parameter_computers.values():
            covered = remaining & set(computer.produced_parameters)
            if covered:
                selected.append(computer)
                remaining -= covered
        if remaining:
            raise UnknownOperatorError(f"missing parameter producers: {sorted(remaining)}")
        return selected
