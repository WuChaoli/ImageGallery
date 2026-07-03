import hashlib
import json
from dataclasses import dataclass
from typing import TypeAlias

from image_gallery.cleaning.errors import OperatorConfigError

OperatorConfigInput: TypeAlias = list[dict[str, dict[str, object]]]


@dataclass(frozen=True)
class ParsedOperatorConfig:
    """单个算子的已解析运行配置。"""

    operator_name: str
    config: dict[str, object]
    config_hash: str


def parse_operator_configs(operator_configs: OperatorConfigInput) -> list[ParsedOperatorConfig]:
    """把用户传入的 list[{operator_name: config}] 解析为稳定结构。"""
    if not isinstance(operator_configs, list) or not operator_configs:
        raise OperatorConfigError("operator_configs must be a non-empty list")

    parsed: list[ParsedOperatorConfig] = []
    seen: set[str] = set()
    for item in operator_configs:
        if not isinstance(item, dict) or len(item) != 1:
            raise OperatorConfigError("each operator config item must contain exactly one operator")

        operator_name, config = next(iter(item.items()))
        if not isinstance(operator_name, str) or not operator_name:
            raise OperatorConfigError("operator_name must be a non-empty string")
        if operator_name in seen:
            raise OperatorConfigError(f"duplicate operator config: {operator_name}")
        if not isinstance(config, dict):
            raise OperatorConfigError(f"config for {operator_name} must be a dict")

        seen.add(operator_name)
        normalized_config = dict(config)
        parsed.append(
            ParsedOperatorConfig(
                operator_name=operator_name,
                config=normalized_config,
                config_hash=hash_config(normalized_config),
            )
        )
    return parsed


def merge_default_config(
    parsed_config: ParsedOperatorConfig,
    default_config: dict[str, object],
) -> ParsedOperatorConfig:
    """合并算子默认配置和用户配置，用户配置优先。"""
    merged = {**default_config, **parsed_config.config}
    return ParsedOperatorConfig(
        operator_name=parsed_config.operator_name,
        config=merged,
        config_hash=hash_config(merged),
    )


def hash_config(config: dict[str, object]) -> str:
    """对配置做稳定 JSON 序列化后生成 sha256。"""
    payload = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
