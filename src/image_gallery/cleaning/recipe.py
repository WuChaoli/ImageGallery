"""YAML 配方加载与编译。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from image_gallery.cleaning._recipe_parser import load_recipe_payload, resolve_operator_name
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
        reg = registry if registry is not None else create_default_registry()
        version, run_defaults, operator_payloads = load_recipe_payload(path, reg)
        operators = [RecipeOperator(use=use, config=config) for use, config in operator_payloads]
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
            full_name = resolve_operator_name(op.use, reg)
            selectors.append({full_name: dict(op.config)})
        return selectors
