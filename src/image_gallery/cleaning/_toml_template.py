"""Cleaner TOML 配置模板渲染。"""

from __future__ import annotations

from typing import cast

from image_gallery.cleaning.selection import OperatorSelectorInput, select_operators
from image_gallery.operators.builtin import create_default_registry
from image_gallery.operators.registry import OperatorRegistry


def build_template(
    operators: object,
    *,
    registry: OperatorRegistry | None = None,
) -> str:
    """为给定 selectors 构造不含密钥的 cleaner TOML 模板。"""
    selected_registry = registry if registry is not None else create_default_registry()
    normalized_operators = _normalize_operators(operators)
    configured = select_operators(
        cast(OperatorSelectorInput, normalized_operators),
        selected_registry,
    )

    lines = ["[operators]"]
    for operator in configured:
        config_items = [
            f"{key} = {_format_value(value)}" for key, value in operator.config.items() if value is not None
        ]
        inline_config = "{ " + ", ".join(config_items) + " }" if config_items else "{}"
        lines.append(f"{operator.operator_name} = {inline_config}")

    lines.extend(
        [
            "",
            "[runtime]",
            "batch_size = 128",
            "fail_fast = false",
            "max_errors = 100",
        ]
    )
    return "\n".join(lines) + "\n"


def _normalize_operators(raw: object) -> list[str]:
    """把模板输入归一化为 selectors 列表。"""
    if isinstance(raw, str):
        return [raw]
    if not isinstance(raw, list) or not raw:
        raise ValueError("template operators must be a non-empty string or list of strings")
    normalized: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item:
            raise ValueError("template operators entries must be non-empty strings")
        normalized.append(item)
    return normalized


def _format_value(value: object) -> str:
    """把基础 Python 值格式化为 TOML 字面量。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_format_value(item) for item in value) + "]"
    raise TypeError(f"unsupported TOML template value: {value!r}")
