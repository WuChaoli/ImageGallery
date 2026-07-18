"""CleanerRecipe 的 YAML 读取与算子短名校验。"""

from __future__ import annotations

from pathlib import Path

import yaml

from image_gallery.operators.registry import OperatorRegistry


def load_recipe_payload(
    path: str | Path,
    registry: OperatorRegistry,
) -> tuple[int, dict[str, object], list[tuple[str, dict[str, object]]]]:
    """读取并校验 YAML recipe 的稳定输入结构。"""
    yaml_path = Path(path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"recipe file not found: {yaml_path}")

    with yaml_path.open(encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise TypeError("recipe YAML root must be a mapping")

    version = int(data.get("version", 1))
    if version != 1:
        raise ValueError(f"unsupported recipe version: {version}; only version 1 is supported")

    run_defaults_raw = data.get("run", {})
    run_defaults = dict(run_defaults_raw) if isinstance(run_defaults_raw, dict) else {}
    operators_raw = data.get("operators", [])
    if not isinstance(operators_raw, list) or not operators_raw:
        raise ValueError("recipe must have at least one operator")

    operators: list[tuple[str, dict[str, object]]] = []
    for item in operators_raw:
        if not isinstance(item, dict) or "use" not in item:
            raise ValueError(f"each operator must be a mapping with 'use' key, got: {item!r}")
        use = str(item["use"])
        resolve_operator_name(use, registry)
        operators.append((use, {key: value for key, value in item.items() if key != "use"}))
    return version, run_defaults, operators


def resolve_operator_name(short_name: str, registry: OperatorRegistry) -> str:
    """校验算子短名并返回注册表中的主标识。"""
    if "." in short_name:
        raise ValueError(f"old long operator name is no longer supported: {short_name}; please use short names")
    all_names = registry.list_operators()
    if short_name in all_names:
        return short_name
    raise ValueError(f"cannot resolve operator short name {short_name!r}; available operators: {all_names}")
