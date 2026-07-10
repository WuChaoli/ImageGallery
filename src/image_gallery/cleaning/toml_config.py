from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from image_gallery.cleaning.policy import (
    ArtifactPolicy,
    BatchPolicy,
    CachePolicy,
    CheckpointPolicy,
    FailurePolicy,
    NodePolicy,
    ResourcePolicy,
    RetryPolicy,
)
from image_gallery.cleaning.selection import OperatorSelectorInput, select_operators
from image_gallery.operators.builtin import create_default_registry
from image_gallery.operators.registry import OperatorRegistry


@dataclass(frozen=True)
class CleanerConfig:
    """从 TOML 解析的清洗配置承载对象。"""

    operators: OperatorSelectorInput
    operator_configs: dict[str, dict[str, object]]
    node_policy: NodePolicy
    operator_policies: dict[str, NodePolicy]

    @classmethod
    def from_toml(cls, path: str | Path) -> "CleanerConfig":
        """从 TOML 文件路径加载配置。"""
        path_obj = Path(path)
        with path_obj.open("rb") as file:
            payload = tomllib.load(file)
        return cls.from_mapping(_as_mapping(payload, str(path_obj)))

    @classmethod
    def from_mapping(cls, payload: dict[str, object]) -> "CleanerConfig":
        """从 TOML 映射对象加载配置。"""
        payload_map = _as_mapping(payload, "root")
        cleaner_payload = _as_mapping(payload_map.get("cleaner", {}), "cleaner")
        operators = _parse_operators(cleaner_payload.get("operators"))
        operator_configs = _parse_operator_configs(payload_map.get("operator"))
        node_policy = _parse_node_policy(payload_map.get("node_policy"), "node_policy")
        operator_policies = _parse_operator_policies(payload_map.get("operator_policies"))
        return cls(
            operators=operators,
            operator_configs=operator_configs,
            node_policy=node_policy,
            operator_policies=operator_policies,
        )


def build_cleaner_toml_template(
    operators: object,
    *,
    registry: OperatorRegistry | None = None,
) -> str:
    """为给定 selectors 构造不含密钥的 cleaner TOML 模板。"""
    selected_registry = registry if registry is not None else create_default_registry()
    normalized_operators = _normalize_template_operators(operators)
    configured = select_operators(cast(OperatorSelectorInput, normalized_operators), selected_registry)

    lines = [
        "[cleaner]",
        f"operators = {_format_toml_list(normalized_operators)}",
        "",
        "[node_policy.batch]",
        "size = 128",
        "",
        "[node_policy.failure]",
        "fail_fast = false",
        "max_errors = 100",
    ]
    for operator in configured:
        lines.extend(
            [
                "",
                "[[operator]]",
                f'name = "{operator.operator_name}"',
            ]
        )
        for key, value in operator.config.items():
            if value is None:
                continue
            lines.append(f"{key} = {_format_toml_value(value)}")
    return "\n".join(lines) + "\n"


def _parse_operator_configs(raw: object) -> dict[str, dict[str, object]]:
    """解析 [[operator]] 中的业务配置。"""
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise ValueError("operator section must be a list")

    parsed: dict[str, dict[str, object]] = {}
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("each operator entry must be a mapping")

        if "name" in item:
            name = item["name"]
            if not isinstance(name, str) or not name:
                raise ValueError("operator name must be a non-empty string")
            config = dict(item)
            config.pop("name")
        elif len(item) == 1:
            name, config_value = next(iter(item.items()))
            if not isinstance(name, str) or not name:
                raise ValueError("operator name must be a non-empty string")
            if not isinstance(config_value, Mapping):
                raise ValueError(f"operator config for {name} must be a mapping")
            config = dict(config_value)
        else:
            raise ValueError("operator entry must contain name field or one operator key")

        if not isinstance(config, dict):
            raise ValueError(f"operator config for {name} must be a mapping")
        parsed[name] = config
    return parsed


def _normalize_template_operators(raw: object) -> list[str]:
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


def _format_toml_list(values: list[str]) -> str:
    """格式化字符串列表为 TOML 数组。"""
    return "[" + ", ".join(f'"{value}"' for value in values) + "]"


def _format_toml_value(value: object) -> str:
    """把基础 Python 值格式化为 TOML 字面量。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_format_toml_value(item) for item in value) + "]"
    if isinstance(value, tuple):
        return "[" + ", ".join(_format_toml_value(item) for item in value) + "]"
    raise TypeError(f"unsupported TOML template value: {value!r}")


def _parse_operators(raw: object) -> OperatorSelectorInput:
    """解析 cleaner section 的 operators 选择字段。"""
    if isinstance(raw, str):
        return [raw]
    if raw is None:
        return ["ALL"]
    if isinstance(raw, list):
        if not all(isinstance(item, str) for item in raw):
            raise ValueError("operators entries must be strings")
        return raw
    raise ValueError("operators must be a string or list of strings")


def _parse_operator_policies(raw: object) -> dict[str, NodePolicy]:
    """解析 operator_policies 分段。"""
    if raw is None:
        return {}
    payload = _as_mapping(raw, "operator_policies")
    policies: dict[str, NodePolicy] = {}
    for operator_name, policy_payload in payload.items():
        if not isinstance(operator_name, str) or not operator_name:
            raise ValueError("operator_policies keys must be non-empty strings")
        policies[operator_name] = _parse_node_policy(policy_payload, f"operator_policies.{operator_name}")
    return policies


def _parse_node_policy(raw: object, scope: str) -> NodePolicy:
    """解析单个 NodePolicy。"""
    payload = _as_mapping(raw, scope, allow_none=True)
    batch = _parse_batch_policy(payload.get("batch"), f"{scope}.batch")
    checkpoint = _parse_checkpoint_policy(payload.get("checkpoint"), f"{scope}.checkpoint")
    cache = _parse_cache_policy(payload.get("cache"), f"{scope}.cache")
    failure = _parse_failure_policy(payload.get("failure"), f"{scope}.failure")
    resources = _parse_resource_policy(payload.get("resources"), f"{scope}.resources")
    artifacts = _parse_artifact_policy(payload.get("artifacts"), f"{scope}.artifacts")
    return NodePolicy(
        batch=batch,
        checkpoint=checkpoint,
        cache=cache,
        failure=failure,
        resources=resources,
        artifacts=artifacts,
    )


def _parse_batch_policy(raw: object, scope: str) -> BatchPolicy:
    payload = _as_mapping(raw, scope, allow_none=True)
    size = payload.get("size", 128)
    if not isinstance(size, int) or size <= 0:
        raise ValueError(f"{scope}.batch.size must be positive integer")
    return BatchPolicy(size=size)


def _parse_checkpoint_policy(raw: object, scope: str) -> CheckpointPolicy:
    payload = _as_mapping(raw, scope, allow_none=True)
    enabled = payload.get("enabled", True)
    strategy = payload.get("strategy", "auto")
    if not isinstance(enabled, bool):
        raise ValueError(f"{scope}.enabled must be bool")
    if not isinstance(strategy, str):
        raise ValueError(f"{scope}.strategy must be string")
    return CheckpointPolicy(enabled=enabled, strategy=strategy)


def _parse_resource_policy(raw: object, scope: str) -> ResourcePolicy:
    payload = _as_mapping(raw, scope, allow_none=True)
    max_workers = payload.get("max_workers", 1)
    device = payload.get("device", "auto")
    if not isinstance(max_workers, int) or max_workers <= 0:
        raise ValueError(f"{scope}.max_workers must be positive integer")
    if not isinstance(device, str):
        raise ValueError(f"{scope}.device must be string")
    return ResourcePolicy(max_workers=max_workers, device=device)


def _parse_cache_policy(raw: object, scope: str) -> CachePolicy:
    payload = _as_mapping(raw, scope, allow_none=True)
    scope_value = payload.get("scope", "system")
    reuse = payload.get("reuse", "run")
    cleanup = payload.get("cleanup", "on_success")
    if not isinstance(scope_value, str):
        raise ValueError(f"{scope}.scope must be string")
    if not isinstance(reuse, str):
        raise ValueError(f"{scope}.reuse must be string")
    if not isinstance(cleanup, str):
        raise ValueError(f"{scope}.cleanup must be string")
    return CachePolicy(scope=scope_value, reuse=reuse, cleanup=cleanup)


def _parse_artifact_policy(raw: object, scope: str) -> ArtifactPolicy:
    payload = _as_mapping(raw, scope, allow_none=True)
    retain_intermediate = payload.get("retain_intermediate", False)
    write_debug_manifest = payload.get("write_debug_manifest", True)
    if not isinstance(retain_intermediate, bool):
        raise ValueError(f"{scope}.retain_intermediate must be bool")
    if not isinstance(write_debug_manifest, bool):
        raise ValueError(f"{scope}.write_debug_manifest must be bool")
    return ArtifactPolicy(retain_intermediate=retain_intermediate, write_debug_manifest=write_debug_manifest)


def _parse_failure_policy(raw: object, scope: str) -> FailurePolicy:
    payload = _as_mapping(raw, scope, allow_none=True)
    fail_fast = payload.get("fail_fast", False)
    max_errors = payload.get("max_errors")
    bad_image_action = payload.get("bad_image_action", "mark_failed")
    if not isinstance(fail_fast, bool):
        raise ValueError(f"{scope}.fail_fast must be bool")
    if max_errors is not None and (not isinstance(max_errors, int) or max_errors < 0):
        raise ValueError(f"{scope}.max_errors must be non-negative int")
    if not isinstance(bad_image_action, str):
        raise ValueError(f"{scope}.bad_image_action must be string")

    retry = _parse_retry_policy(payload.get("retry"), f"{scope}.retry")
    return FailurePolicy(
        fail_fast=fail_fast,
        max_errors=max_errors,
        bad_image_action=bad_image_action,
        retry=retry,
    )


def _parse_retry_policy(raw: object, scope: str) -> RetryPolicy:
    payload = _as_mapping(raw, scope, allow_none=True)
    max_attempts = payload.get("max_attempts", 1)
    backoff_seconds = payload.get("backoff_seconds", 0.0)
    retry_on = payload.get("retry_on", ("io_error", "temporary_error", "artifact_commit_error"))
    if not isinstance(max_attempts, int) or max_attempts < 1:
        raise ValueError(f"{scope}.max_attempts must be positive int")
    if not isinstance(backoff_seconds, (float, int)) or backoff_seconds < 0:
        raise ValueError(f"{scope}.backoff_seconds must be non-negative number")
    if not isinstance(retry_on, (tuple, list)) or not all(isinstance(item, str) for item in retry_on):
        raise ValueError(f"{scope}.retry_on must be tuple of strings")
    return RetryPolicy(
        max_attempts=max_attempts,
        backoff_seconds=float(backoff_seconds),
        retry_on=tuple(retry_on),
    )


def _as_mapping(value: object, scope: str, allow_none: bool = False) -> dict[str, object]:
    """把 TOML 段转换为映射。"""
    if value is None:
        if allow_none:
            return {}
        raise ValueError(f"{scope} must be a mapping, got none")
    if isinstance(value, Mapping):
        return dict(value)
    raise ValueError(f"{scope} must be a mapping")
