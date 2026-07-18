"""ParameterComputer 配置解析的私有共享边界。"""

from collections.abc import Iterable, Mapping

from image_gallery.cleaning.config import hash_config
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


def resolve_parameter_computer_configs(
    operator_configs: Iterable[tuple[OperatorSpec, Mapping[str, object]]],
    registry: OperatorRegistry,
) -> dict[str, tuple[dict[str, object], str]]:
    """将逻辑算子配置投影到参数依赖闭包内的 computer。"""
    configs: dict[str, tuple[dict[str, object], str]] = {}

    def collect_computer_names(parameter_name: str, seen: set[str]) -> set[str]:
        computer = registry.get_parameter_producer(parameter_name)
        if computer.name in seen:
            return set()
        seen.add(computer.name)
        names = {computer.name}
        for required_parameter in computer.required_parameters:
            names.update(collect_computer_names(required_parameter, seen))
        return names

    for spec, config in operator_configs:
        computer_names: set[str] = set()
        for required_parameter in spec.required_parameters:
            computer_names.update(collect_computer_names(required_parameter, set()))

        for computer_name in sorted(computer_names):
            computer = registry.get_parameter_computer(computer_name)
            projected_config = {key: config[key] for key in sorted(computer.config_parameters) if key in config}
            config_hash = hash_config(projected_config) if projected_config else "default"
            next_config = (projected_config, config_hash)
            existing_config = configs.get(computer.name)
            if existing_config is not None and existing_config != next_config:
                raise ValueError(f"conflicting parameter computer config: {computer.name}")
            configs[computer.name] = next_config
    return configs
