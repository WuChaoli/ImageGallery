"""数学区间语法解析与包含判断。"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

# 匹配区间语法：左右括号 + 数字 + 逗号 + 数字 + 右括号
_INTERVAL_PATTERN = re.compile(
    r"^\s*([\[\(])\s*(-?[\d.]+(?:[eE][+-]?\d+)?)\s*,\s*(-?[\d.]+(?:[eE][+-]?\d+)?)\s*([\]\)])\s*$"
)


@dataclass(frozen=True)
class ActionRange:
    """表示一个数学区间，用于定义清洗动作的阈值范围。

    Attributes:
        lower: 区间下界。
        upper: 区间上界。
        lower_inclusive: 下界是否包含（True 表示 `[`，False 表示 `(`）。
        upper_inclusive: 上界是否包含（True 表示 `]`，False 表示 `)`）。
    """

    lower: float
    upper: float
    lower_inclusive: bool
    upper_inclusive: bool

    @classmethod
    def from_string(cls, text: str) -> ActionRange:
        """从字符串解析区间语法，如 ``"[0, 0.3]"`` 或 ``"(0.3, 0.6]"``。

        支持闭区间 ``[]``、开区间 ``()`` 以及混合形式 ``(]`` / ``[)``。
        不接受无括号语法和无穷值。

        Args:
            text: 区间字符串。

        Returns:
            解析后的 ActionRange 实例。

        Raises:
            ValueError: 语法无效或包含无穷值。
        """
        match = _INTERVAL_PATTERN.match(text)
        if match is None:
            raise ValueError(f"invalid interval syntax: {text!r}; expected format like '[0, 0.3]' or '(0.3, 0.6]'")

        left_bracket, lower_str, upper_str, right_bracket = match.groups()
        lower = float(lower_str)
        upper = float(upper_str)

        # 拒绝无穷值
        if math.isinf(lower) or math.isinf(upper):
            raise ValueError(f"infinity is not supported in interval: {text!r}")
        if math.isnan(lower) or math.isnan(upper):
            raise ValueError(f"NaN is not supported in interval: {text!r}")

        lower_inclusive = left_bracket == "["
        upper_inclusive = right_bracket == "]"

        return cls(
            lower=lower,
            upper=upper,
            lower_inclusive=lower_inclusive,
            upper_inclusive=upper_inclusive,
        )

    def contains(self, value: float) -> bool:
        """判断给定值是否落在区间内。

        Args:
            value: 待判断的数值。

        Returns:
            值在区间内返回 True，否则返回 False。
        """
        if self.lower_inclusive:
            lower_ok = value >= self.lower
        else:
            lower_ok = value > self.lower

        if self.upper_inclusive:
            upper_ok = value <= self.upper
        else:
            upper_ok = value < self.upper

        return lower_ok and upper_ok
