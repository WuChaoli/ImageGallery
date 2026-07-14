from collections.abc import Mapping

from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import ConfiguredOperatorSpec, OperatorSpec

OperatorSelectorInput = str | list[str | Mapping[str, object] | OperatorSpec | ConfiguredOperatorSpec]
OperatorOverrides = list[dict[str, dict[str, object]]] | dict[str, dict[str, object]] | None


def select_operators(
    operators: OperatorSelectorInput,
    registry: OperatorRegistry,
    overrides: OperatorOverrides = None,
    override: bool = False,
) -> list[ConfiguredOperatorSpec]:
    """按名称/分类扩展并绑定默认配置，返回已配置算子列表。"""
    selected_names: list[str] = []
    merged_configs: dict[str, dict[str, object]] = {}
    override_map = _normalize_overrides(overrides)

    configured_specs: dict[str, ConfiguredOperatorSpec] = {}
    for selector, inline_config, configured_spec in _normalize_operator_selectors(operators):
        if configured_spec is not None:
            _register_temporary_spec(configured_spec.spec, registry, override=override)
            operator_name = configured_spec.operator_name
            if operator_name not in merged_configs:
                selected_names.append(operator_name)
            elif not override:
                continue
            merged_configs[operator_name] = dict(configured_spec.config)
            configured_specs[operator_name] = configured_spec
            continue

        assert selector is not None
        expanded = _expand_selector(selector, registry)
        if inline_config is not None and len(expanded) != 1:
            raise ValueError("inline operator config can only target one operator")
        for operator_name in expanded:
            config = _select_operator_config(
                inline_config=inline_config,
                override_config=override_map.get(operator_name),
                override=override,
            )
            if operator_name not in merged_configs:
                selected_names.append(operator_name)
            elif not override:
                continue
            merged_configs[operator_name] = config
    return [
        configured_specs.get(
            operator_name,
            ConfiguredOperatorSpec.from_spec(
                registry.get_operator(operator_name),
                merged_configs[operator_name],
                source="selection",
            ),
        )
        for operator_name in selected_names
    ]


def _expand_selector(selector: str, registry: OperatorRegistry) -> list[str]:
    """展开输入 token 为算子名列表。"""
    if not isinstance(selector, str) or not selector:
        raise TypeError("selector must be a non-empty string")

    if selector.upper() == "ALL":
        return [spec.name for spec in registry.list_operator_specs()]

    if selector in registry.list_operators():
        return [selector]

    category = selector.upper()
    categories = {name.upper() for name in registry.list_categories()}
    if category in categories:
        return [spec.name for spec in registry.list_operator_specs() if spec.category.upper() == category]

    if "." in selector:
        raise ValueError(
            f"old long operator name is no longer supported: {selector}; "
            f"please use short names. available operators: {registry.list_operators()}; "
            f"available categories: {registry.list_categories()}"
        )

    raise ValueError(
        f"unknown selector: {selector}; available operators: {registry.list_operators()}; "
        f"available categories: {registry.list_categories()}"
    )


def _normalize_operator_selectors(
    operators: OperatorSelectorInput,
) -> list[tuple[str | None, dict[str, object] | None, ConfiguredOperatorSpec | None]]:
    """把用户输入转为可扩展的选择器与配置对。"""
    if isinstance(operators, str):
        return [(operators, None, None)]
    if not isinstance(operators, list):
        raise TypeError("operators must be string or list")

    normalized: list[tuple[str | None, dict[str, object] | None, ConfiguredOperatorSpec | None]] = []
    for item in operators:
        if isinstance(item, str):
            normalized.append((item, None, None))
            continue
        if isinstance(item, ConfiguredOperatorSpec):
            normalized.append((None, None, item))
            continue
        if isinstance(item, OperatorSpec):
            normalized.append(
                (
                    None,
                    None,
                    ConfiguredOperatorSpec.from_spec(item, {}, source="python"),
                )
            )
            continue
        if not isinstance(item, Mapping):
            raise TypeError("each operator selector must be a string or mapping")
        if len(item) != 1:
            raise ValueError("each operator selector mapping must contain one item")
        key, value = next(iter(item.items()))
        if not isinstance(key, str) or not key:
            raise TypeError("operator selector key must be non-empty string")
        if value is None:
            normalized.append((key, None, None))
            continue
        if not isinstance(value, Mapping):
            raise TypeError(f"operator config for {key} must be a mapping")
        normalized.append((key, dict(value), None))
    return normalized


def _register_temporary_spec(spec: OperatorSpec, registry: OperatorRegistry, *, override: bool) -> None:
    """把 Python 直接传入的 spec 注册为本次选择可用的临时条目。"""
    if spec.name in registry.list_operators() and not override:
        raise ValueError(f"operator spec already exists: {spec.name}; pass override=True to replace it")
    registry.register_operator(spec)


def _normalize_overrides(overrides: OperatorOverrides) -> dict[str, dict[str, object]]:
    """把可选覆盖配置归一化为映射。"""
    if overrides is None:
        return {}
    if isinstance(overrides, dict):
        raw_overrides = [overrides]
    elif isinstance(overrides, list):
        raw_overrides = overrides
    else:
        raise TypeError("overrides must be dict, list, or None")

    normalized: dict[str, dict[str, object]] = {}
    for override in raw_overrides:
        if not isinstance(override, Mapping):
            raise TypeError("each override item must be a mapping")
        for operator_name, raw_config in override.items():
            if not isinstance(operator_name, str) or not operator_name:
                raise TypeError("override operator name must be non-empty string")
            if not isinstance(raw_config, Mapping):
                raise TypeError(f"override config for {operator_name} must be a mapping")
            normalized[operator_name] = dict(raw_config)
    return normalized


def _select_operator_config(
    inline_config: dict[str, object] | None,
    override_config: dict[str, object] | None,
    override: bool,
) -> dict[str, object]:
    """按优先级合并算子配置。"""
    if inline_config is None:
        if override_config is None:
            return {}
        return dict(override_config)
    if override_config is None:
        return dict(inline_config)
    if override:
        return {**inline_config, **override_config}
    return {**override_config, **inline_config}
