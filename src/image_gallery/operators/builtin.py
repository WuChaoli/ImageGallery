import pandas as pd

from image_gallery.operators.computers.metadata import ImageMetadataComputer
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


def create_default_registry() -> OperatorRegistry:
    """创建包含第一版 v3 基础逻辑算子和参数计算单元的注册表。"""
    registry = OperatorRegistry()
    registry.register_parameter_computer(ImageMetadataComputer())
    for spec in _builtin_specs():
        registry.register_operator(spec)
    return registry


def _builtin_specs() -> list[OperatorSpec]:
    """返回第一批 v3 内置逻辑算子规格。"""
    return [
        OperatorSpec(
            name="format.decode_check",
            category="format",
            required_parameters=["decode_ok", "decode_error"],
            evaluation_columns=["decode_action", "decode_reason"],
            default_config={"action": "drop"},
            action_column="decode_action",
            reason_column="decode_reason",
            evaluator=evaluate_decode_check,
        ),
        OperatorSpec(
            name="size.dimension_check",
            category="size",
            required_parameters=["width", "height"],
            evaluation_columns=["dimension_action", "dimension_reason"],
            default_config={"min_width": 1, "min_height": 1, "action": "drop"},
            action_column="dimension_action",
            reason_column="dimension_reason",
            evaluator=evaluate_dimension_check,
        ),
    ]


def evaluate_decode_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 decode_ok 生成解码检查结果。"""
    action = str(config.get("action", "drop"))
    failed = ~parameter_table["decode_ok"].fillna(False).astype(bool)
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "decode_action": failed.map(lambda value: action if value else "keep"),
            "decode_reason": parameter_table["decode_error"].where(failed, ""),
        }
    )


def evaluate_dimension_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 width、height 和阈值生成尺寸检查结果。"""
    min_width = _as_int(config.get("min_width", 1))
    min_height = _as_int(config.get("min_height", 1))
    action = str(config.get("action", "drop"))
    widths = pd.to_numeric(parameter_table["width"], errors="coerce").fillna(0)
    heights = pd.to_numeric(parameter_table["height"], errors="coerce").fillna(0)
    failed = (widths < min_width) | (heights < min_height)
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "dimension_action": failed.map(lambda value: action if value else "keep"),
            "dimension_reason": failed.map(lambda value: f"smaller than {min_width}x{min_height}" if value else ""),
        }
    )


def _as_int(value: object) -> int:
    """把配置值转换为 int。"""
    if isinstance(value, (str, bytes, int, float)):
        return int(value)
    raise TypeError(f"expected int-compatible config value, got {type(value).__name__}")
