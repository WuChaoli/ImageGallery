import pandas as pd

from image_gallery.operators.backends.fastdup_backend import FastdupSimilarityBackend
from image_gallery.operators.backends.hash_backend import ImageHashBackend
from image_gallery.operators.backends.opencv_backend import OpenCVQualityBackend
from image_gallery.operators.backends.pillow_backend import PillowMetadataBackend
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


def create_default_registry() -> OperatorRegistry:
    """创建包含第一版内置算子和后端的注册表。"""
    registry = OperatorRegistry()
    registry.register_backend(PillowMetadataBackend())
    registry.register_backend(OpenCVQualityBackend())
    registry.register_backend(ImageHashBackend())
    registry.register_backend(FastdupSimilarityBackend())

    for spec in _builtin_specs():
        registry.register_operator(spec)
    return registry


def _builtin_specs() -> list[OperatorSpec]:
    """返回 BasicCleaner 第一批内置算子规格。"""
    return [
        OperatorSpec(
            name="format.decode_check",
            category="format",
            backend_name="pillow_metadata_backend",
            parameter_columns=["decode_ok", "decode_error"],
            evaluation_columns=["decode_action", "decode_reason"],
            default_config={"action": "drop"},
            action_column="decode_action",
            reason_column="decode_reason",
            evaluator=evaluate_decode_check,
        ),
        OperatorSpec(
            name="size.dimension_check",
            category="size",
            backend_name="pillow_metadata_backend",
            parameter_columns=["width", "height"],
            evaluation_columns=["dimension_action", "dimension_reason"],
            default_config={"min_width": 1, "min_height": 1, "action": "drop"},
            action_column="dimension_action",
            reason_column="dimension_reason",
            evaluator=evaluate_dimension_check,
        ),
        OperatorSpec(
            name="quality.blur_check",
            category="quality",
            backend_name="opencv_quality_backend",
            parameter_columns=["blur_score"],
            evaluation_columns=["blur_score", "blur_action", "blur_reason"],
            default_config={"threshold": 30.0, "action": "review"},
            action_column="blur_action",
            reason_column="blur_reason",
            evaluator=lambda parameter_table, config: evaluate_threshold_check(
                parameter_table,
                score_column="blur_score",
                output_prefix="blur",
                config=config,
                lower_is_bad=True,
            ),
        ),
        OperatorSpec(
            name="quality.brightness_check",
            category="quality",
            backend_name="opencv_quality_backend",
            parameter_columns=["brightness_score"],
            evaluation_columns=["brightness_score", "brightness_action", "brightness_reason"],
            default_config={"min_threshold": 20.0, "max_threshold": 235.0, "action": "review"},
            action_column="brightness_action",
            reason_column="brightness_reason",
            evaluator=evaluate_brightness_check,
        ),
        OperatorSpec(
            name="quality.contrast_check",
            category="quality",
            backend_name="opencv_quality_backend",
            parameter_columns=["contrast_score"],
            evaluation_columns=["contrast_score", "contrast_action", "contrast_reason"],
            default_config={"threshold": 10.0, "action": "review"},
            action_column="contrast_action",
            reason_column="contrast_reason",
            evaluator=lambda parameter_table, config: evaluate_threshold_check(
                parameter_table,
                score_column="contrast_score",
                output_prefix="contrast",
                config=config,
                lower_is_bad=True,
            ),
        ),
        OperatorSpec(
            name="duplicate.exact_duplicate_check",
            category="duplicate",
            backend_name="image_hash_backend",
            parameter_columns=["content_hash", "phash", "exact_duplicate_group_id"],
            evaluation_columns=["exact_duplicate_group_id", "exact_duplicate_action", "exact_duplicate_reason"],
            default_config={"action": "review"},
            action_column="exact_duplicate_action",
            reason_column="exact_duplicate_reason",
            evaluator=evaluate_exact_duplicate_check,
        ),
        OperatorSpec(
            name="duplicate.near_duplicate_check",
            category="duplicate",
            backend_name="fastdup_similarity_backend",
            parameter_columns=["near_duplicate_group_id", "nearest_neighbor_id", "nearest_neighbor_score"],
            evaluation_columns=[
                "near_duplicate_group_id",
                "near_duplicate_score",
                "near_duplicate_action",
                "near_duplicate_reason",
            ],
            default_config={"threshold": 0.95, "action": "review"},
            action_column="near_duplicate_action",
            reason_column="near_duplicate_reason",
            evaluator=evaluate_near_duplicate_check,
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


def evaluate_threshold_check(
    parameter_table: pd.DataFrame,
    score_column: str,
    output_prefix: str,
    config: dict[str, object],
    lower_is_bad: bool,
) -> pd.DataFrame:
    """通用阈值类质量检查。"""
    threshold = _as_float(config.get("threshold", 0.0))
    action = str(config.get("action", "review"))
    scores = parameter_table[score_column].astype(float)
    failed = scores < threshold if lower_is_bad else scores > threshold
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            score_column: scores,
            f"{output_prefix}_action": failed.map(lambda value: action if value else "keep"),
            f"{output_prefix}_reason": failed.map(
                lambda value: f"{score_column} outside threshold {threshold}" if value else ""
            ),
        }
    )


def evaluate_brightness_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据亮度上下限生成亮度检查结果。"""
    min_threshold = _as_float(config.get("min_threshold", 20.0))
    max_threshold = _as_float(config.get("max_threshold", 235.0))
    action = str(config.get("action", "review"))
    scores = parameter_table["brightness_score"].astype(float)
    failed = (scores < min_threshold) | (scores > max_threshold)
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "brightness_score": scores,
            "brightness_action": failed.map(lambda value: action if value else "keep"),
            "brightness_reason": failed.map(
                lambda value: f"brightness outside {min_threshold}-{max_threshold}" if value else ""
            ),
        }
    )


def evaluate_exact_duplicate_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 exact_duplicate_group_id 生成完全重复检查结果。"""
    action = str(config.get("action", "review"))
    group_ids = parameter_table["exact_duplicate_group_id"].fillna("").astype(str)
    failed = group_ids != ""
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "exact_duplicate_group_id": group_ids,
            "exact_duplicate_action": failed.map(lambda value: action if value else "keep"),
            "exact_duplicate_reason": failed.map(lambda value: "exact duplicate" if value else ""),
        }
    )


def evaluate_near_duplicate_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 near duplicate 参数生成近重复检查结果。"""
    action = str(config.get("action", "review"))
    threshold = _as_float(config.get("threshold", 0.95))
    scores = parameter_table["nearest_neighbor_score"].fillna(0.0).astype(float)
    group_ids = parameter_table["near_duplicate_group_id"].fillna("").astype(str)
    failed = (group_ids != "") & (scores >= threshold)
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "near_duplicate_group_id": group_ids,
            "near_duplicate_score": scores,
            "near_duplicate_action": failed.map(lambda value: action if value else "keep"),
            "near_duplicate_reason": failed.map(lambda value: "near duplicate" if value else ""),
        }
    )


def _as_int(value: object) -> int:
    """把配置值转换为 int。"""
    if isinstance(value, (str, bytes, int, float)):
        return int(value)
    raise TypeError(f"expected int-compatible config value, got {type(value).__name__}")


def _as_float(value: object) -> float:
    """把配置值转换为 float。"""
    if isinstance(value, (str, bytes, int, float)):
        return float(value)
    raise TypeError(f"expected float-compatible config value, got {type(value).__name__}")
