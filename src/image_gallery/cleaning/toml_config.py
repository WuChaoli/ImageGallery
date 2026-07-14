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
        return cls.from_mapping(_as_mapping(payload, str(path_obj)))

    @classmethod
    def from_mapping(cls, payload: dict[str, object]) -> "CleanerConfig":
        """从 TOML 映射对象加载配置。"""
        payload_map = _as_mapping(payload, "root")
        has_select = "select" in payload_map
        has_operators = "operators" in payload_map
        if has_select and has_operators:
            raise ValueError("select and operators sections are mutually exclusive")

        selectors = _parse_selectors(payload_map.get("select"), payload_map.get("operators"))
        operator_configs, operator_policies = _parse_operators_section(payload_map.get("operators"))
        node_policy = _parse_runtime_policy(payload_map.get("runtime"), "runtime")
        return cls(
            selectors=selectors,
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
        "[operators]",
    ]
    for operator in configured:
        config_items = [
            f"{key} = {_format_toml_value(value)}" for key, value in operator.config.items() if value is not None
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


def _parse_selectors(select_raw: object, operators_raw: object) -> OperatorSelectorInput:
    """解析 select/operators 两种互斥选择来源。"""
    if operators_raw is not None:
        operators_payload = _as_mapping(operators_raw, "operators")
        return list(operators_payload)
    if select_raw is None:
        return ["ALL"]

    select_payload = _as_mapping(select_raw, "select")
    categories = select_payload.get("categories")
    if isinstance(categories, str) and categories:
        return [categories]
    if isinstance(categories, list) and all(isinstance(item, str) and item for item in categories):
        return categories
    raise ValueError("select.categories must be a non-empty string or list of strings")


def _parse_operators_section(raw: object) -> tuple[dict[str, dict[str, object]], dict[str, NodePolicy]]:
    """解析 operators 段中的算子配置和算子级 runtime 覆盖。"""
    if raw is None:
        return {}, {}

    payload = _as_mapping(raw, "operators")
    operator_configs: dict[str, dict[str, object]] = {}
    operator_policies: dict[str, NodePolicy] = {}
    for operator_name, raw_config in payload.items():
        if not isinstance(operator_name, str) or not operator_name:
            raise ValueError("operators keys must be non-empty strings")
        config = _as_mapping(raw_config, f"operators.{operator_name}")
        runtime_config = config.pop("runtime", None)
        operator_configs[operator_name] = config
        if runtime_config is not None:
            operator_policies[operator_name] = _parse_runtime_policy(
                runtime_config,
                f"operators.{operator_name}.runtime",
            )
    return operator_configs, operator_policies


def _parse_runtime_policy(raw: object, scope: str) -> NodePolicy:
    """解析拍平 runtime 字段为 NodePolicy。"""
    payload = _as_mapping(raw, scope, allow_none=True)
    nested_payload: dict[str, object] = {
        "batch": {},
        "checkpoint": {},
        "cache": {},
        "failure": {},
        "resources": {},
        "artifacts": {},
    }
    field_map = {
        "batch_size": ("batch", "size"),
        "checkpoint_enabled": ("checkpoint", "enabled"),
        "checkpoint_strategy": ("checkpoint", "strategy"),
        "cache_scope": ("cache", "scope"),
        "cache_reuse": ("cache", "reuse"),
        "cache_cleanup": ("cache", "cleanup"),
        "fail_fast": ("failure", "fail_fast"),
        "max_errors": ("failure", "max_errors"),
        "bad_image_action": ("failure", "bad_image_action"),
        "retry_max_attempts": ("failure", "retry.max_attempts"),
        "retry_backoff_seconds": ("failure", "retry.backoff_seconds"),
        "retry_on": ("failure", "retry.retry_on"),
        "max_workers": ("resources", "max_workers"),
        "device": ("resources", "device"),
        "retain_intermediate": ("artifacts", "retain_intermediate"),
        "write_debug_manifest": ("artifacts", "write_debug_manifest"),
    }
    for key, value in payload.items():
        if key not in field_map:
            raise ValueError(f"{scope}.{key} is not a supported runtime field")
        section, target = field_map[key]
        section_payload = _as_mapping(nested_payload[section], f"{scope}.{section}")
        if "." in target:
            nested_key, leaf_key = target.split(".", maxsplit=1)
            nested = _as_mapping(section_payload.get(nested_key, {}), f"{scope}.{section}.{nested_key}")
            nested[leaf_key] = value
            section_payload[nested_key] = nested
        else:
            section_payload[target] = value
        nested_payload[section] = section_payload

    return _parse_node_policy(nested_payload, scope)


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
