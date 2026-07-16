"""YAML 配方加载与编译。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from image_gallery.operators.builtin import create_default_registry
from image_gallery.operators.registry import OperatorRegistry


@dataclass(frozen=True)
class RecipeOperator:
    """YAML 配方中的单个算子配置块。

    Attributes:
        use: 算子短名（如 ``"blur"``）。
        config: 该算子的配置字典（rules / drop / review / action 等）。
    """

    use: str
    config: dict[str, object]


@dataclass(frozen=True)
class CleanerRecipe:
    """从 YAML 文件加载的清洗配方。

    Attributes:
        version: 配方版本号，当前仅支持 1。
        run_defaults: 运行参数默认值（output_dir, cache_root 等）。
        operators: 算子配置列表。
    """

    version: int
    run_defaults: dict[str, object]
    operators: list[RecipeOperator]

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
        *,
        registry: OperatorRegistry | None = None,
    ) -> CleanerRecipe:
        """从 YAML 文件加载配方。

        Args:
            path: YAML 文件路径。
            registry: 可选算子注册表，用于校验短名解析；缺省使用内置注册表。

        Returns:
            解析后的 CleanerRecipe 实例。

        Raises:
            ValueError: version 不为 1 或 operators 为空。
            FileNotFoundError: 文件不存在。
        """
        yaml_path = Path(path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"recipe file not found: {yaml_path}")

        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise TypeError("recipe YAML root must be a mapping")

        version = int(data.get("version", 1))
        if version != 1:
            raise ValueError(f"unsupported recipe version: {version}; only version 1 is supported")

        run_defaults_raw = data.get("run", {})
        run_defaults: dict[str, object] = dict(run_defaults_raw) if isinstance(run_defaults_raw, dict) else {}

        operators_raw = data.get("operators", [])
        if not isinstance(operators_raw, list) or len(operators_raw) == 0:
            raise ValueError("recipe must have at least one operator")

        reg = registry if registry is not None else create_default_registry()
        operators: list[RecipeOperator] = []
        for item in operators_raw:
            if not isinstance(item, dict) or "use" not in item:
                raise ValueError(f"each operator must be a mapping with 'use' key, got: {item!r}")
            use = str(item["use"])
            config = {k: v for k, v in item.items() if k != "use"}
            # 校验短名可解析
            _resolve_operator_name(use, reg)
            operators.append(RecipeOperator(use=use, config=config))

        return cls(version=version, run_defaults=run_defaults, operators=operators)

    def compile_selectors(
        self,
        *,
        registry: OperatorRegistry | None = None,
    ) -> list[dict[str, object]]:
        """将 YAML operators 编译为 ``select_operators()`` 可消费的 selector 列表。

        支持三种算子模式：
        - **rules 区间**: ``{use: blur, rules: {drop: "[0, 0.3]", review: "(0.3, 0.6]"}}``
        - **绝对阈值**: ``{use: dimension, drop: {min_width: 256}, review: {min_width: 512}}``
        - **布尔 action**: ``{use: decode, action: drop}``

        Args:
            registry: 可选算子注册表；缺省使用内置注册表。

        Returns:
            selector 列表，每项为 ``{full_operator_name: config_dict}``。
        """
        reg = registry if registry is not None else create_default_registry()
        selectors: list[dict[str, object]] = []
        for op in self.operators:
            full_name = _resolve_operator_name(op.use, reg)
            selectors.append({full_name: dict(op.config)})
        return selectors


def _resolve_operator_name(short_name: str, registry: OperatorRegistry) -> str:
    """校验算子短名并返回注册表中的主标识。

    Args:
        short_name: 算子短名。
        registry: 算子注册表。

    Returns:
        注册表中的算子名。

    Raises:
        ValueError: 无法解析短名。
    """
    if "." in short_name:
        raise ValueError(f"old long operator name is no longer supported: {short_name}; please use short names")

    all_names = registry.list_operators()
    if short_name in all_names:
        return short_name

    raise ValueError(f"cannot resolve operator short name {short_name!r}; available operators: {all_names}")
