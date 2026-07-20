"""Cleaner TOML 配置的公开解析入口。"""

from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from image_gallery.cleaning._toml_policy import as_mapping, parse_runtime_policy
from image_gallery.cleaning._toml_template import build_template
from image_gallery.cleaning.policy import NodePolicy
from image_gallery.cleaning.selection import OperatorSelectorInput
from image_gallery.operators.registry import OperatorRegistry


@dataclass(frozen=True)
class CleanerConfig:
    """从 TOML 解析的清洗配置承载对象。"""

    selectors: OperatorSelectorInput
    operator_configs: dict[str, dict[str, object]]
    node_policy: NodePolicy
    operator_policies: dict[str, NodePolicy]

    @property
    def operators(self) -> OperatorSelectorInput:
        """返回传给清洗运行时的算子选择器。"""
        return self.selectors

    @classmethod
    def from_toml(cls, path: str | Path) -> "CleanerConfig":
        """从 TOML 文件路径加载配置。"""
        path_obj = Path(path)
        with path_obj.open("rb") as file:
            payload = tomllib.load(file)
        return cls.from_mapping(as_mapping(payload, str(path_obj)))

    @classmethod
    def from_mapping(cls, payload: dict[str, object]) -> "CleanerConfig":
        """从 TOML 映射对象加载配置。"""
        payload_map = as_mapping(payload, "root")
        has_select = "select" in payload_map
        has_operators = "operators" in payload_map
        if has_select and has_operators:
            raise ValueError("select and operators sections are mutually exclusive")

        selectors = _parse_selectors(
            payload_map.get("select"),
            payload_map.get("operators"),
        )
        operator_configs, operator_policies = _parse_operators_section(payload_map.get("operators"))
        return cls(
            selectors=selectors,
            operator_configs=operator_configs,
            node_policy=parse_runtime_policy(payload_map.get("runtime"), "runtime"),
            operator_policies=operator_policies,
        )


def build_cleaner_toml_template(
    operators: object,
    *,
    registry: OperatorRegistry | None = None,
) -> str:
    """为给定 selectors 构造不含密钥的 cleaner TOML 模板。"""
    return build_template(operators, registry=registry)


def _parse_selectors(
    select_raw: object,
    operators_raw: object,
) -> OperatorSelectorInput:
    """解析 select/operators 两种互斥选择来源。"""
    if operators_raw is not None:
        return list(as_mapping(operators_raw, "operators"))
    if select_raw is None:
        return ["ALL"]

    select_payload = as_mapping(select_raw, "select")
    categories = select_payload.get("categories")
    if isinstance(categories, str) and categories:
        return [categories]
    if isinstance(categories, list) and all(isinstance(item, str) and item for item in categories):
        return categories
    raise ValueError("select.categories must be a non-empty string or list of strings")


def _parse_operators_section(
    raw: object,
) -> tuple[dict[str, dict[str, object]], dict[str, NodePolicy]]:
    """解析 operators 段中的算子配置和算子级 runtime 覆盖。"""
    if raw is None:
        return {}, {}

    payload = as_mapping(raw, "operators")
    operator_configs: dict[str, dict[str, object]] = {}
    operator_policies: dict[str, NodePolicy] = {}
    for operator_name, raw_config in payload.items():
        if not isinstance(operator_name, str) or not operator_name:
            raise ValueError("operators keys must be non-empty strings")
        config = as_mapping(raw_config, f"operators.{operator_name}")
        runtime_config = config.pop("runtime", None)
        operator_configs[operator_name] = config
        if runtime_config is not None:
            operator_policies[operator_name] = parse_runtime_policy(
                runtime_config,
                f"operators.{operator_name}.runtime",
            )
    return operator_configs, operator_policies
