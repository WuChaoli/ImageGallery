"""基于 ActionRange 区间规则的双级动作评估。"""

from __future__ import annotations

from typing import cast

import pandas as pd

from image_gallery.cleaning.action_range import ActionRange
from image_gallery.operators.metric_spec import MetricSpec


def evaluate_with_rules(
    parameter_table: pd.DataFrame,
    metric_column: str,
    metric_spec: MetricSpec,
    rules: dict[str, ActionRange],
) -> pd.Series:
    """按 drop > review > keep 优先级评估每行的动作。

    对 ``parameter_table`` 中的每一行，根据指标值和 ActionRange 规则确定动作。
    优先级：drop > review > keep —— 如果一个值同时命中 drop 和 review 区间，取 drop。

    Args:
        parameter_table: 包含指标列的 DataFrame。
        metric_column: 指标列名（如 ``"blur_score"``）。
        metric_spec: 该指标的 MetricSpec，用于决定值类型和归一化方式。
        rules: 动作到 ActionRange 的映射，键为 ``"drop"`` 或 ``"review"``。

    Returns:
        与 parameter_table 等长的 Series，值为 ``"drop"`` / ``"review"`` / ``"keep"``。
    """
    raw_values = cast(pd.Series, pd.to_numeric(parameter_table[metric_column], errors="coerce"))

    # 对 relative 指标做归一化：绝对值 → [0, 1]
    is_relative = (
        metric_spec.value_type == "relative"
        and metric_spec.absolute_min is not None
        and metric_spec.absolute_max is not None
    )
    if is_relative:
        assert metric_spec.absolute_min is not None  # narrowed by is_relative
        assert metric_spec.absolute_max is not None  # narrowed by is_relative
        abs_min: float = metric_spec.absolute_min
        abs_max: float = metric_spec.absolute_max
        abs_range = abs_max - abs_min
        if abs_range == 0:
            normalized = cast(pd.Series, raw_values - abs_min)
        else:
            normalized = cast(pd.Series, (raw_values - abs_min) / abs_range)
    else:
        normalized = raw_values

    # 按优先级 drop > review 评估
    actions = pd.Series("keep", index=parameter_table.index)
    # 先评 review（低优先级），再评 drop（高优先级覆盖）
    for action_name in ("review", "drop"):
        if action_name in rules:
            action_range = rules[action_name]
            mask = normalized.apply(
                lambda value, ar=action_range: _safe_contains(ar, value),
            )
            actions = actions.where(~mask, action_name)

    return actions


def _safe_contains(action_range: ActionRange, value: float) -> bool:
    """安全判断值是否在区间内，NaN 返回 False。"""
    if pd.isna(value):
        return False
    return action_range.contains(float(value))
