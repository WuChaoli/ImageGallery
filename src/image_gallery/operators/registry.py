from image_gallery.cleaning.errors import UnknownOperatorError
from image_gallery.operators.computers.base import ParameterComputer
from image_gallery.operators.spec import OperatorSpec


class OperatorRegistry:
    """逻辑算子和参数计算单元注册表。"""

    def __init__(self) -> None:
        self._operators: dict[str, OperatorSpec] = {}
        self._parameter_computers: dict[str, ParameterComputer] = {}
        self._parameter_producers: dict[str, str] = {}

    def register_operator(self, spec: OperatorSpec) -> None:
        """注册逻辑算子。"""
        self._operators[spec.name] = spec

    def register_parameter_computer(self, computer: ParameterComputer) -> None:
        """注册参数计算单元，并索引参数生产者。"""
        for parameter_name in computer.produced_parameters:
            existing_computer = self._parameter_producers.get(parameter_name)
            if existing_computer is not None and existing_computer != computer.name:
                raise ValueError(
                    f"parameter already has producer: {parameter_name} ({existing_computer}, {computer.name})"
                )
        self._parameter_computers[computer.name] = computer
        for parameter_name in computer.produced_parameters:
            self._parameter_producers[parameter_name] = computer.name

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

    def list_operator_specs(self) -> list[OperatorSpec]:
        """按注册顺序返回当前可用逻辑算子规格。"""
        return list(self._operators.values())

    def list_categories(self) -> list[str]:
        """返回当前 registry 的逻辑算子 category（去重并排序）。"""
        return sorted({spec.category for spec in self._operators.values()})

    def list_parameter_computers(self) -> list[ParameterComputer]:
        """返回注册顺序下的参数计算单元。"""
        return list(self._parameter_computers.values())

    def get_parameter_producer(self, parameter_name: str) -> ParameterComputer:
        """返回生产指定参数的计算单元。"""
        try:
            computer_name = self._parameter_producers[parameter_name]
        except KeyError as exc:
            raise UnknownOperatorError(f"missing parameter producer: {parameter_name}") from exc
        return self.get_parameter_computer(computer_name)

    def find_computers_for_parameters(self, parameter_names: set[str]) -> list[ParameterComputer]:
        """按参数需求返回可覆盖这些参数的计算单元。"""
        required = set(parameter_names)
        selected: list[ParameterComputer] = []
        selected_names: set[str] = set()
        covered_parameters: set[str] = set()

        while True:
            remaining = required - covered_parameters
            if not remaining:
                return [computer for computer in self._parameter_computers.values() if computer.name in selected_names]

            made_progress = False
            for computer in self._parameter_computers.values():
                if computer.name in selected_names:
                    continue
                covered = remaining & set(computer.produced_parameters)
                if not covered:
                    continue
                selected.append(computer)
                selected_names.add(computer.name)
                covered_parameters.update(covered)
                required.update(computer.required_parameters)
                made_progress = True

            if not made_progress:
                raise UnknownOperatorError(f"missing parameter producers: {sorted(remaining)}")
