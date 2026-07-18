"""Cleaner TOML 的运行策略解析与类型校验。"""

from __future__ import annotations

from collections.abc import Mapping

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


def parse_runtime_policy(raw: object, scope: str) -> NodePolicy:
    """解析拍平 runtime 字段为 NodePolicy。"""
    payload = as_mapping(raw, scope, allow_none=True)
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
        section_payload = as_mapping(nested_payload[section], f"{scope}.{section}")
        if "." in target:
            nested_key, leaf_key = target.split(".", maxsplit=1)
            nested = as_mapping(
                section_payload.get(nested_key, {}),
                f"{scope}.{section}.{nested_key}",
            )
            nested[leaf_key] = value
            section_payload[nested_key] = nested
        else:
            section_payload[target] = value
        nested_payload[section] = section_payload

    return _parse_node_policy(nested_payload, scope)


def as_mapping(value: object, scope: str, allow_none: bool = False) -> dict[str, object]:
    """把 TOML 段转换为映射。"""
    if value is None:
        if allow_none:
            return {}
        raise ValueError(f"{scope} must be a mapping, got none")
    if isinstance(value, Mapping):
        return dict(value)
    raise ValueError(f"{scope} must be a mapping")


def _parse_node_policy(raw: object, scope: str) -> NodePolicy:
    """解析单个 NodePolicy。"""
    payload = as_mapping(raw, scope, allow_none=True)
    return NodePolicy(
        batch=_parse_batch_policy(payload.get("batch"), f"{scope}.batch"),
        checkpoint=_parse_checkpoint_policy(payload.get("checkpoint"), f"{scope}.checkpoint"),
        cache=_parse_cache_policy(payload.get("cache"), f"{scope}.cache"),
        failure=_parse_failure_policy(payload.get("failure"), f"{scope}.failure"),
        resources=_parse_resource_policy(payload.get("resources"), f"{scope}.resources"),
        artifacts=_parse_artifact_policy(payload.get("artifacts"), f"{scope}.artifacts"),
    )


def _parse_batch_policy(raw: object, scope: str) -> BatchPolicy:
    payload = as_mapping(raw, scope, allow_none=True)
    size = payload.get("size", 128)
    if not isinstance(size, int) or size <= 0:
        raise ValueError(f"{scope}.batch.size must be positive integer")
    return BatchPolicy(size=size)


def _parse_checkpoint_policy(raw: object, scope: str) -> CheckpointPolicy:
    payload = as_mapping(raw, scope, allow_none=True)
    enabled = payload.get("enabled", True)
    strategy = payload.get("strategy", "auto")
    if not isinstance(enabled, bool):
        raise TypeError(f"{scope}.enabled must be bool")
    if not isinstance(strategy, str):
        raise TypeError(f"{scope}.strategy must be string")
    return CheckpointPolicy(enabled=enabled, strategy=strategy)


def _parse_resource_policy(raw: object, scope: str) -> ResourcePolicy:
    payload = as_mapping(raw, scope, allow_none=True)
    max_workers = payload.get("max_workers", 1)
    device = payload.get("device", "auto")
    if not isinstance(max_workers, int) or max_workers <= 0:
        raise ValueError(f"{scope}.max_workers must be positive integer")
    if not isinstance(device, str):
        raise TypeError(f"{scope}.device must be string")
    return ResourcePolicy(max_workers=max_workers, device=device)


def _parse_cache_policy(raw: object, scope: str) -> CachePolicy:
    payload = as_mapping(raw, scope, allow_none=True)
    scope_value = payload.get("scope", "system")
    reuse = payload.get("reuse", "run")
    cleanup = payload.get("cleanup", "on_success")
    if not isinstance(scope_value, str):
        raise TypeError(f"{scope}.scope must be string")
    if not isinstance(reuse, str):
        raise TypeError(f"{scope}.reuse must be string")
    if not isinstance(cleanup, str):
        raise TypeError(f"{scope}.cleanup must be string")
    return CachePolicy(scope=scope_value, reuse=reuse, cleanup=cleanup)


def _parse_artifact_policy(raw: object, scope: str) -> ArtifactPolicy:
    payload = as_mapping(raw, scope, allow_none=True)
    retain_intermediate = payload.get("retain_intermediate", False)
    write_debug_manifest = payload.get("write_debug_manifest", True)
    if not isinstance(retain_intermediate, bool):
        raise TypeError(f"{scope}.retain_intermediate must be bool")
    if not isinstance(write_debug_manifest, bool):
        raise TypeError(f"{scope}.write_debug_manifest must be bool")
    return ArtifactPolicy(
        retain_intermediate=retain_intermediate,
        write_debug_manifest=write_debug_manifest,
    )


def _parse_failure_policy(raw: object, scope: str) -> FailurePolicy:
    payload = as_mapping(raw, scope, allow_none=True)
    fail_fast = payload.get("fail_fast", False)
    max_errors = payload.get("max_errors")
    bad_image_action = payload.get("bad_image_action", "mark_failed")
    if not isinstance(fail_fast, bool):
        raise TypeError(f"{scope}.fail_fast must be bool")
    if max_errors is not None and (not isinstance(max_errors, int) or max_errors < 0):
        raise ValueError(f"{scope}.max_errors must be non-negative int")
    if not isinstance(bad_image_action, str):
        raise TypeError(f"{scope}.bad_image_action must be string")
    return FailurePolicy(
        fail_fast=fail_fast,
        max_errors=max_errors,
        bad_image_action=bad_image_action,
        retry=_parse_retry_policy(payload.get("retry"), f"{scope}.retry"),
    )


def _parse_retry_policy(raw: object, scope: str) -> RetryPolicy:
    payload = as_mapping(raw, scope, allow_none=True)
    max_attempts = payload.get("max_attempts", 1)
    backoff_seconds = payload.get("backoff_seconds", 0.0)
    retry_on = payload.get(
        "retry_on",
        ("io_error", "temporary_error", "artifact_commit_error"),
    )
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
