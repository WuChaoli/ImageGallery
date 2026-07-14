"""算子指标元数据描述，支持绝对值、相对值和分类三种类型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricSpec:
    """描述算子用户可调指标的类型、范围和方向。

    Attributes:
        name: 指标名（如 ``"blur_score"``、``"min_width"``）。
        value_type: 指标类型，``"absolute"`` / ``"relative"`` / ``"categorical"``。
        direction: 方向语义，``"higher_better"`` / ``"lower_better"`` / ``"categorical"``。
        absolute_min: 仅 relative 类型使用，绝对范围下界。
        absolute_max: 仅 relative 类型使用，绝对范围上界。
    """

    name: str
    value_type: str
    direction: str
    absolute_min: float | None = None
    absolute_max: float | None = None


def relative_to_absolute(metric: MetricSpec, relative_value: float) -> float:
    """将 [0, 1] 相对值映射到 MetricSpec 的绝对范围。

    Args:
        metric: 指标规格，必须是 ``value_type="relative"`` 且已设定绝对范围。
        relative_value: [0, 1] 之间的相对值。

    Returns:
        映射后的绝对值。

    Raises:
        ValueError: 相对值超出 [0, 1] 或指标未设定绝对范围。
        TypeError: 指标不是 relative 类型。
    """
    if metric.value_type != "relative":
        raise TypeError(f"relative_to_absolute only supports value_type='relative', got {metric.value_type!r}")
    if metric.absolute_min is None or metric.absolute_max is None:
        raise ValueError(f"metric {metric.name!r} is missing absolute_min/absolute_max")
    if relative_value < 0.0 or relative_value > 1.0:
        raise ValueError(f"relative_value {relative_value} is out of [0, 1] range for metric {metric.name!r}")
    return metric.absolute_min + relative_value * (metric.absolute_max - metric.absolute_min)
