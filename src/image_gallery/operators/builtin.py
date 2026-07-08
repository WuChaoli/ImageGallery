import pandas as pd

from image_gallery.operators.computers.derived import TableDerivedComputer
from image_gallery.operators.computers.duplicate import DuplicateGroupComputer, PerceptualDuplicateGroupComputer
from image_gallery.operators.computers.hash import ImageHashComputer, ImagePerceptualHashComputer
from image_gallery.operators.computers.metadata import ImageMetadataComputer
from image_gallery.operators.computers.quality import ImageQualityComputer
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


def create_default_registry() -> OperatorRegistry:
    """创建包含第一版 v3 基础逻辑算子和参数计算单元的注册表。"""
    registry = OperatorRegistry()
    registry.register_parameter_computer(ImageMetadataComputer())
    registry.register_parameter_computer(TableDerivedComputer())
    registry.register_parameter_computer(ImageQualityComputer())
    registry.register_parameter_computer(ImageHashComputer())
    registry.register_parameter_computer(ImagePerceptualHashComputer())
    registry.register_parameter_computer(DuplicateGroupComputer())
    registry.register_parameter_computer(PerceptualDuplicateGroupComputer())
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
        OperatorSpec(
            name="size.aspect_ratio_check",
            category="size",
            required_parameters=["aspect_ratio"],
            evaluation_columns=["aspect_ratio", "aspect_ratio_action", "aspect_ratio_reason"],
            default_config={"min_ratio": 0.2, "max_ratio": 5.0, "action": "review"},
            action_column="aspect_ratio_action",
            reason_column="aspect_ratio_reason",
            evaluator=evaluate_aspect_ratio_check,
        ),
        OperatorSpec(
            name="size.megapixel_check",
            category="size",
            required_parameters=["megapixels"],
            evaluation_columns=["megapixels", "megapixel_action", "megapixel_reason"],
            default_config={"min_megapixels": 0.01, "max_megapixels": None, "action": "review"},
            action_column="megapixel_action",
            reason_column="megapixel_reason",
            evaluator=evaluate_megapixel_check,
        ),
        OperatorSpec(
            name="quality.blur_check",
            category="quality",
            required_parameters=["blur_score"],
            evaluation_columns=["blur_score", "blur_action", "blur_reason"],
            default_config={"min_score": 100.0, "action": "review"},
            action_column="blur_action",
            reason_column="blur_reason",
            evaluator=evaluate_blur_check,
        ),
        OperatorSpec(
            name="quality.brightness_check",
            category="quality",
            required_parameters=["brightness_score"],
            evaluation_columns=["brightness_score", "brightness_action", "brightness_reason"],
            default_config={"min_score": 30.0, "max_score": 225.0, "action": "review"},
            action_column="brightness_action",
            reason_column="brightness_reason",
            evaluator=evaluate_brightness_check,
        ),
        OperatorSpec(
            name="quality.contrast_check",
            category="quality",
            required_parameters=["contrast_score"],
            evaluation_columns=["contrast_score", "contrast_action", "contrast_reason"],
            default_config={"min_score": 10.0, "action": "review"},
            action_column="contrast_action",
            reason_column="contrast_reason",
            evaluator=evaluate_contrast_check,
        ),
        OperatorSpec(
            name="content.blank_image_check",
            category="content",
            required_parameters=["blank_score"],
            evaluation_columns=["blank_score", "blank_action", "blank_reason"],
            default_config={"threshold": 0.98, "action": "drop"},
            action_column="blank_action",
            reason_column="blank_reason",
            evaluator=evaluate_blank_image_check,
        ),
        OperatorSpec(
            name="duplicate.exact_duplicate_check",
            category="duplicate",
            required_parameters=["exact_duplicate_group_id", "exact_duplicate_count"],
            evaluation_columns=[
                "exact_duplicate_group_id",
                "exact_duplicate_count",
                "exact_duplicate_action",
                "exact_duplicate_reason",
            ],
            default_config={"keep": "first", "action": "drop"},
            action_column="exact_duplicate_action",
            reason_column="exact_duplicate_reason",
            evaluator=evaluate_exact_duplicate_check,
        ),
        OperatorSpec(
            name="duplicate.perceptual_duplicate_check",
            category="duplicate",
            required_parameters=[
                "perceptual_duplicate_group_id",
                "perceptual_duplicate_count",
                "perceptual_duplicate_distance",
            ],
            evaluation_columns=[
                "perceptual_duplicate_group_id",
                "perceptual_duplicate_count",
                "perceptual_duplicate_distance",
                "perceptual_duplicate_action",
                "perceptual_duplicate_reason",
            ],
            default_config={"max_distance": 10, "keep": "first", "action": "drop"},
            action_column="perceptual_duplicate_action",
            reason_column="perceptual_duplicate_reason",
            evaluator=evaluate_perceptual_duplicate_check,
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


def evaluate_aspect_ratio_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 aspect_ratio 生成宽高比检查结果。"""
    min_ratio = _as_float(config.get("min_ratio", 0.2))
    max_ratio = _as_float(config.get("max_ratio", 5.0))
    action = str(config.get("action", "review"))
    ratios = pd.to_numeric(parameter_table["aspect_ratio"], errors="coerce")
    failed = ratios.notna() & ((ratios < min_ratio) | (ratios > max_ratio))
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "aspect_ratio": ratios,
            "aspect_ratio_action": failed.map(lambda value: action if value else "keep"),
            "aspect_ratio_reason": failed.map(
                lambda value: f"aspect ratio outside {min_ratio}..{max_ratio}" if value else ""
            ),
        }
    )


def evaluate_megapixel_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 megapixels 生成像素量检查结果。"""
    min_megapixels = _as_float(config.get("min_megapixels", 0.01))
    max_value = config.get("max_megapixels")
    max_megapixels = None if max_value is None else _as_float(max_value)
    action = str(config.get("action", "review"))
    megapixels = pd.to_numeric(parameter_table["megapixels"], errors="coerce")
    failed = megapixels.notna() & (megapixels < min_megapixels)
    if max_megapixels is not None:
        failed = failed | (megapixels.notna() & (megapixels > max_megapixels))
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "megapixels": megapixels,
            "megapixel_action": failed.map(lambda value: action if value else "keep"),
            "megapixel_reason": failed.map(lambda value: "megapixels outside configured range" if value else ""),
        }
    )


def evaluate_blur_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 blur_score 生成模糊检查结果。"""
    min_score = _as_float(config.get("min_score", 100.0))
    action = str(config.get("action", "review"))
    scores = pd.to_numeric(parameter_table["blur_score"], errors="coerce")
    failed = scores.notna() & (scores < min_score)
    return _score_threshold_frame(
        parameter_table["image_id"], scores, failed, "blur", action, f"blur score below {min_score}"
    )


def evaluate_brightness_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 brightness_score 生成亮度检查结果。"""
    min_score = _as_float(config.get("min_score", 30.0))
    max_score = _as_float(config.get("max_score", 225.0))
    action = str(config.get("action", "review"))
    scores = pd.to_numeric(parameter_table["brightness_score"], errors="coerce")
    failed = scores.notna() & ((scores < min_score) | (scores > max_score))
    return _score_threshold_frame(
        parameter_table["image_id"],
        scores,
        failed,
        "brightness",
        action,
        f"brightness outside {min_score}..{max_score}",
    )


def evaluate_contrast_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 contrast_score 生成对比度检查结果。"""
    min_score = _as_float(config.get("min_score", 10.0))
    action = str(config.get("action", "review"))
    scores = pd.to_numeric(parameter_table["contrast_score"], errors="coerce")
    failed = scores.notna() & (scores < min_score)
    return _score_threshold_frame(
        parameter_table["image_id"], scores, failed, "contrast", action, f"contrast score below {min_score}"
    )


def evaluate_blank_image_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 blank_score 生成空白图检查结果。"""
    threshold = _as_float(config.get("threshold", 0.98))
    action = str(config.get("action", "drop"))
    scores = pd.to_numeric(parameter_table["blank_score"], errors="coerce")
    failed = scores.notna() & (scores >= threshold)
    return _score_threshold_frame(
        parameter_table["image_id"], scores, failed, "blank", action, f"blank score at least {threshold}"
    )


def evaluate_exact_duplicate_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据完全重复组生成去重结果。"""
    keep = str(config.get("keep", "first"))
    if keep != "first":
        raise ValueError("duplicate.exact_duplicate_check only supports keep='first'")
    action = str(config.get("action", "drop"))
    groups = parameter_table["exact_duplicate_group_id"].fillna("").astype(str)
    counts = pd.to_numeric(parameter_table["exact_duplicate_count"], errors="coerce").fillna(1).astype(int)

    seen_groups: set[str] = set()
    actions: list[str] = []
    reasons: list[str] = []
    for group_id, count in zip(groups.tolist(), counts.tolist(), strict=True):
        if not group_id or count <= 1:
            actions.append("keep")
            reasons.append("")
            continue
        if group_id not in seen_groups:
            seen_groups.add(group_id)
            actions.append("keep")
            reasons.append("")
            continue
        actions.append(action)
        reasons.append(f"duplicate in group {group_id}")

    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "exact_duplicate_group_id": groups,
            "exact_duplicate_count": counts,
            "exact_duplicate_action": actions,
            "exact_duplicate_reason": reasons,
        }
    )


def evaluate_perceptual_duplicate_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据视觉近重复组生成去重结果。"""
    keep = str(config.get("keep", "first"))
    if keep != "first":
        raise ValueError("duplicate.perceptual_duplicate_check only supports keep='first'")
    action = str(config.get("action", "drop"))
    if action != "drop":
        raise ValueError("duplicate.perceptual_duplicate_check only supports action='drop'")

    groups = parameter_table["perceptual_duplicate_group_id"].fillna("").astype(str)
    counts = pd.to_numeric(parameter_table["perceptual_duplicate_count"], errors="coerce").fillna(1).astype(int)
    distances = pd.to_numeric(parameter_table["perceptual_duplicate_distance"], errors="coerce")

    seen_groups: set[str] = set()
    actions: list[str] = []
    reasons: list[str] = []
    for group_id, count, distance in zip(groups.tolist(), counts.tolist(), distances.tolist(), strict=True):
        if not group_id or count <= 1:
            actions.append("keep")
            reasons.append("")
            continue
        if group_id not in seen_groups:
            seen_groups.add(group_id)
            actions.append("keep")
            reasons.append("")
            continue
        actions.append(action)
        reasons.append(f"duplicate in group {group_id} distance {int(distance)}")

    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "perceptual_duplicate_group_id": groups,
            "perceptual_duplicate_count": counts,
            "perceptual_duplicate_distance": distances,
            "perceptual_duplicate_action": actions,
            "perceptual_duplicate_reason": reasons,
        }
    )


def _score_threshold_frame(
    image_ids: pd.Series,
    scores: pd.Series,
    failed: pd.Series,
    prefix: str,
    action: str,
    reason: str,
) -> pd.DataFrame:
    """构造分数阈值类算子的评估结果。"""
    return pd.DataFrame(
        {
            "image_id": image_ids,
            f"{prefix}_score": scores,
            f"{prefix}_action": failed.map(lambda value: action if value else "keep"),
            f"{prefix}_reason": failed.map(lambda value: reason if value else ""),
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
