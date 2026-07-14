from dataclasses import replace
from typing import cast

import pandas as pd

from image_gallery.cleaning.preview_policy import PreviewPolicy
from image_gallery.operators.computers.border import ImageBorderComputer
from image_gallery.operators.computers.derived import TableDerivedComputer
from image_gallery.operators.computers.duplicate import DuplicateGroupComputer, PerceptualDuplicateGroupComputer
from image_gallery.operators.computers.hash import ImageHashComputer, ImagePerceptualHashComputer
from image_gallery.operators.computers.metadata import ImageFormatDetailComputer, ImageMetadataComputer
from image_gallery.operators.computers.quality import ImageQualityComputer, ImageQualityDetailComputer
from image_gallery.operators.computers.semantic import SemanticDuplicateGroupComputer, SemanticEmbeddingComputer
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.semantic_provider import SemanticEmbeddingProvider
from image_gallery.operators.spec import OperatorSpec


def create_default_registry(
    semantic_providers: dict[str, SemanticEmbeddingProvider] | None = None,
) -> OperatorRegistry:
    """创建包含第一版 v3 基础逻辑算子和参数计算单元的注册表。"""
    registry = OperatorRegistry()
    registry.register_parameter_computer(ImageMetadataComputer())
    registry.register_parameter_computer(TableDerivedComputer())
    registry.register_parameter_computer(ImageQualityComputer())
    registry.register_parameter_computer(ImageQualityDetailComputer())
    registry.register_parameter_computer(ImageBorderComputer())
    registry.register_parameter_computer(ImageFormatDetailComputer())
    registry.register_parameter_computer(ImageHashComputer())
    registry.register_parameter_computer(ImagePerceptualHashComputer())
    registry.register_parameter_computer(DuplicateGroupComputer())
    registry.register_parameter_computer(PerceptualDuplicateGroupComputer())
    registry.register_parameter_computer(SemanticEmbeddingComputer(semantic_providers))
    registry.register_parameter_computer(SemanticDuplicateGroupComputer())
    for spec in _builtin_specs():
        registry.register_operator(spec)
    return registry


def _builtin_specs() -> list[OperatorSpec]:
    """返回第一批 v3 内置逻辑算子规格。"""
    specs = [
        OperatorSpec(
            name="decode",
            category="format",
            required_parameters=["decode_ok", "decode_error"],
            evaluation_columns=["decode_action", "decode_reason"],
            default_config={"action": "drop"},
            action_column="decode_action",
            reason_column="decode_reason",
            evaluator=evaluate_decode_check,
        ),
        OperatorSpec(
            name="dimension",
            category="size",
            required_parameters=["width", "height"],
            evaluation_columns=["dimension_action", "dimension_reason"],
            default_config={"min_width": 1, "min_height": 1, "action": "drop"},
            action_column="dimension_action",
            reason_column="dimension_reason",
            evaluator=evaluate_dimension_check,
        ),
        OperatorSpec(
            name="aspect_ratio",
            category="size",
            required_parameters=["aspect_ratio"],
            evaluation_columns=["aspect_ratio", "aspect_ratio_action", "aspect_ratio_reason"],
            default_config={"min_ratio": 0.2, "max_ratio": 5.0, "action": "review"},
            action_column="aspect_ratio_action",
            reason_column="aspect_ratio_reason",
            evaluator=evaluate_aspect_ratio_check,
        ),
        OperatorSpec(
            name="megapixel",
            category="size",
            required_parameters=["megapixels"],
            evaluation_columns=["megapixels", "megapixel_action", "megapixel_reason"],
            default_config={"min_megapixels": 0.01, "max_megapixels": None, "action": "review"},
            action_column="megapixel_action",
            reason_column="megapixel_reason",
            evaluator=evaluate_megapixel_check,
        ),
        OperatorSpec(
            name="blur",
            category="quality",
            required_parameters=["blur_score"],
            evaluation_columns=["blur_score", "blur_action", "blur_reason"],
            default_config={"min_score": 100.0, "action": "review"},
            action_column="blur_action",
            reason_column="blur_reason",
            evaluator=evaluate_blur_check,
        ),
        OperatorSpec(
            name="brightness",
            category="quality",
            required_parameters=["brightness_score"],
            evaluation_columns=["brightness_score", "brightness_action", "brightness_reason"],
            default_config={"min_score": 30.0, "max_score": 225.0, "action": "review"},
            action_column="brightness_action",
            reason_column="brightness_reason",
            evaluator=evaluate_brightness_check,
        ),
        OperatorSpec(
            name="contrast",
            category="quality",
            required_parameters=["contrast_score"],
            evaluation_columns=["contrast_score", "contrast_action", "contrast_reason"],
            default_config={"min_score": 10.0, "action": "review"},
            action_column="contrast_action",
            reason_column="contrast_reason",
            evaluator=evaluate_contrast_check,
        ),
        OperatorSpec(
            name="blank",
            category="content",
            required_parameters=["blank_score"],
            evaluation_columns=["blank_score", "blank_action", "blank_reason"],
            default_config={"threshold": 0.98, "action": "drop"},
            action_column="blank_action",
            reason_column="blank_reason",
            evaluator=evaluate_blank_image_check,
        ),
        OperatorSpec(
            name="exposure",
            category="quality",
            required_parameters=["dark_pixel_ratio", "bright_pixel_ratio", "clipped_pixel_ratio"],
            evaluation_columns=[
                "dark_pixel_ratio",
                "bright_pixel_ratio",
                "clipped_pixel_ratio",
                "exposure_action",
                "exposure_reason",
            ],
            default_config={
                "max_dark_pixel_ratio": 0.95,
                "max_bright_pixel_ratio": 0.95,
                "max_clipped_pixel_ratio": 0.98,
                "action": "review",
            },
            action_column="exposure_action",
            reason_column="exposure_reason",
            evaluator=evaluate_exposure_check,
        ),
        OperatorSpec(
            name="noise",
            category="quality",
            required_parameters=["noise_score"],
            evaluation_columns=["noise_score", "noise_action", "noise_reason"],
            default_config={"max_score": 0.75, "action": "review"},
            action_column="noise_action",
            reason_column="noise_reason",
            evaluator=evaluate_noise_check,
        ),
        OperatorSpec(
            name="mono_color",
            category="content",
            required_parameters=["mono_color_score"],
            evaluation_columns=["mono_color_score", "mono_color_action", "mono_color_reason"],
            default_config={"threshold": 0.98, "action": "review"},
            action_column="mono_color_action",
            reason_column="mono_color_reason",
            evaluator=evaluate_mono_color_check,
        ),
        OperatorSpec(
            name="border_padding",
            category="content",
            required_parameters=["border_padding_ratio", "border_padding_sides", "border_padding_color"],
            evaluation_columns=[
                "border_padding_ratio",
                "border_padding_sides",
                "border_padding_color",
                "border_padding_action",
                "border_padding_reason",
            ],
            default_config={
                "max_ratio": 0.25,
                "min_side_ratio": 0.08,
                "colors": ["white", "black", "solid"],
                "action": "review",
            },
            action_column="border_padding_action",
            reason_column="border_padding_reason",
            evaluator=evaluate_border_padding_check,
        ),
        OperatorSpec(
            name="animated",
            category="format",
            required_parameters=["frame_count", "animated"],
            evaluation_columns=["frame_count", "animated", "animated_action", "animated_reason"],
            default_config={"action": "review"},
            action_column="animated_action",
            reason_column="animated_reason",
            evaluator=evaluate_animated_image_check,
        ),
        OperatorSpec(
            name="orientation",
            category="metadata",
            required_parameters=["exif_orientation", "orientation_risk"],
            evaluation_columns=[
                "exif_orientation",
                "orientation_risk",
                "orientation_action",
                "orientation_reason",
            ],
            default_config={"action": "review"},
            action_column="orientation_action",
            reason_column="orientation_reason",
            evaluator=evaluate_orientation_check,
        ),
        OperatorSpec(
            name="exact_duplicate",
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
            name="perceptual_duplicate",
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
        OperatorSpec(
            name="semantic_duplicate",
            category="duplicate",
            required_parameters=[
                "semantic_duplicate_group_id",
                "semantic_duplicate_count",
                "semantic_duplicate_score",
                "semantic_duplicate_nearest_image_id",
            ],
            evaluation_columns=[
                "semantic_duplicate_group_id",
                "semantic_duplicate_count",
                "semantic_duplicate_score",
                "semantic_duplicate_nearest_image_id",
                "semantic_duplicate_action",
                "semantic_duplicate_reason",
            ],
            default_config={
                "threshold": 0.92,
                "keep": "first",
                "action": "drop",
                "provider": "onnx_dinov2_small",
                "model_id": "onnx-community/dinov2-small-ONNX",
                "index": "faiss_flat_ip",
                "batch_size": 32,
            },
            action_column="semantic_duplicate_action",
            reason_column="semantic_duplicate_reason",
            evaluator=evaluate_semantic_duplicate_check,
        ),
    ]

    return [_to_builtin_preview_spec(spec) for spec in specs]


def _to_builtin_preview_spec(spec: OperatorSpec) -> OperatorSpec:
    """为内置算子补齐预览策略默认值。"""
    policies = {
        "decode": PreviewPolicy(default_actions=["drop"], caption_columns=["decode_reason"]),
        "animated": PreviewPolicy(
            default_actions=["review"], caption_columns=["frame_count", "animated_reason"]
        ),
        "dimension": PreviewPolicy(
            default_actions=["drop"], caption_columns=["width", "height", "dimension_reason"]
        ),
        "aspect_ratio": PreviewPolicy(
            default_actions=["review"],
            caption_columns=["aspect_ratio", "aspect_ratio_reason"],
            sort_by=["aspect_ratio"],
        ),
        "megapixel": PreviewPolicy(
            default_actions=["review"], caption_columns=["megapixels", "megapixel_reason"], sort_by=["megapixels"]
        ),
        "blur": PreviewPolicy(
            default_actions=["drop", "review"], caption_columns=["blur_score", "blur_reason"], sort_by=["blur_score"]
        ),
        "brightness": PreviewPolicy(
            default_actions=["review"],
            caption_columns=["brightness_score", "brightness_reason"],
            sort_by=["brightness_score"],
        ),
        "contrast": PreviewPolicy(
            default_actions=["review"],
            caption_columns=["contrast_score", "contrast_reason"],
            sort_by=["contrast_score"],
        ),
        "exposure": PreviewPolicy(
            default_actions=["review"],
            caption_columns=["dark_pixel_ratio", "bright_pixel_ratio", "clipped_pixel_ratio", "exposure_reason"],
        ),
        "noise": PreviewPolicy(
            default_actions=["review"],
            caption_columns=["noise_score", "noise_reason"],
            sort_by=["noise_score"],
            ascending=False,
        ),
        "blank": PreviewPolicy(
            default_actions=["drop", "review"],
            caption_columns=["blank_score", "blank_reason"],
            sort_by=["blank_score"],
            ascending=False,
        ),
        "mono_color": PreviewPolicy(
            default_actions=["review"],
            caption_columns=["mono_color_score", "mono_color_reason"],
            sort_by=["mono_color_score"],
            ascending=False,
        ),
        "border_padding": PreviewPolicy(
            default_actions=["review"],
            caption_columns=[
                "border_padding_ratio",
                "border_padding_sides",
                "border_padding_color",
                "border_padding_reason",
            ],
        ),
        "orientation": PreviewPolicy(
            default_actions=["review"], caption_columns=["exif_orientation", "orientation_risk", "orientation_reason"]
        ),
        "exact_duplicate": PreviewPolicy(
            default_actions=["drop", "review"], groupby="exact_duplicate_group_id", include_group_context=True
        ),
        "perceptual_duplicate": PreviewPolicy(
            default_actions=["drop", "review"],
            caption_columns=["perceptual_duplicate_distance"],
            groupby="perceptual_duplicate_group_id",
            include_group_context=True,
        ),
        "semantic_duplicate": PreviewPolicy(
            default_actions=["drop", "review"],
            caption_columns=["semantic_duplicate_score", "semantic_duplicate_nearest_image_id"],
            groupby="semantic_duplicate_group_id",
            include_group_context=True,
        ),
    }
    return replace(spec, preview_policy=policies[spec.name])


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
    widths = cast(pd.Series, pd.to_numeric(parameter_table["width"], errors="coerce")).fillna(0)
    heights = cast(pd.Series, pd.to_numeric(parameter_table["height"], errors="coerce")).fillna(0)
    failed = cast(pd.Series, (widths < min_width) | (heights < min_height))
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
    ratios = cast(pd.Series, pd.to_numeric(parameter_table["aspect_ratio"], errors="coerce"))
    failed = cast(pd.Series, ratios.notna() & ((ratios < min_ratio) | (ratios > max_ratio)))
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
    megapixels = cast(pd.Series, pd.to_numeric(parameter_table["megapixels"], errors="coerce"))
    failed = cast(pd.Series, megapixels.notna() & (megapixels < min_megapixels))
    if max_megapixels is not None:
        failed = cast(pd.Series, failed | (megapixels.notna() & (megapixels > max_megapixels)))
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
    scores = cast(pd.Series, pd.to_numeric(parameter_table["blur_score"], errors="coerce"))
    failed = cast(pd.Series, scores.notna() & (scores < min_score))
    return _score_threshold_frame(
        cast(pd.Series, parameter_table["image_id"]), scores, failed, "blur", action, f"blur score below {min_score}"
    )


def evaluate_brightness_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 brightness_score 生成亮度检查结果。"""
    min_score = _as_float(config.get("min_score", 30.0))
    max_score = _as_float(config.get("max_score", 225.0))
    action = str(config.get("action", "review"))
    scores = cast(pd.Series, pd.to_numeric(parameter_table["brightness_score"], errors="coerce"))
    failed = cast(pd.Series, scores.notna() & ((scores < min_score) | (scores > max_score)))
    return _score_threshold_frame(
        cast(pd.Series, parameter_table["image_id"]),
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
    scores = cast(pd.Series, pd.to_numeric(parameter_table["contrast_score"], errors="coerce"))
    failed = cast(pd.Series, scores.notna() & (scores < min_score))
    return _score_threshold_frame(
        cast(pd.Series, parameter_table["image_id"]), scores, failed, "contrast", action,
        f"contrast score below {min_score}"
    )


def evaluate_blank_image_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 blank_score 生成空白图检查结果。"""
    threshold = _as_float(config.get("threshold", 0.98))
    action = str(config.get("action", "drop"))
    scores = cast(pd.Series, pd.to_numeric(parameter_table["blank_score"], errors="coerce"))
    failed = cast(pd.Series, scores.notna() & (scores >= threshold))
    return _score_threshold_frame(
        cast(pd.Series, parameter_table["image_id"]), scores, failed, "blank", action,
        f"blank score at least {threshold}"
    )


def evaluate_exposure_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据暗部、亮部和截断像素比例生成曝光检查结果。"""
    max_dark = _as_float(config.get("max_dark_pixel_ratio", 0.95))
    max_bright = _as_float(config.get("max_bright_pixel_ratio", 0.95))
    max_clipped = _as_float(config.get("max_clipped_pixel_ratio", 0.98))
    action = str(config.get("action", "review"))
    dark = cast(pd.Series, pd.to_numeric(parameter_table["dark_pixel_ratio"], errors="coerce"))
    bright = cast(pd.Series, pd.to_numeric(parameter_table["bright_pixel_ratio"], errors="coerce"))
    clipped = cast(pd.Series, pd.to_numeric(parameter_table["clipped_pixel_ratio"], errors="coerce"))
    failed = cast(pd.Series, (dark > max_dark) | (bright > max_bright) | (clipped > max_clipped))
    reasons = [
        _exposure_reason(dark_value, bright_value, clipped_value, max_dark, max_bright, max_clipped)
        if failed_value
        else ""
        for dark_value, bright_value, clipped_value, failed_value in zip(
            dark.tolist(), bright.tolist(), clipped.tolist(), failed.tolist(), strict=True
        )
    ]
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "dark_pixel_ratio": dark,
            "bright_pixel_ratio": bright,
            "clipped_pixel_ratio": clipped,
            "exposure_action": failed.map(lambda value: action if value else "keep"),
            "exposure_reason": reasons,
        }
    )


def evaluate_noise_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 noise_score 生成噪声检查结果。"""
    max_score = _as_float(config.get("max_score", 0.75))
    action = str(config.get("action", "review"))
    scores = cast(pd.Series, pd.to_numeric(parameter_table["noise_score"], errors="coerce"))
    failed = cast(pd.Series, scores.notna() & (scores > max_score))
    return _score_threshold_frame(
        cast(pd.Series, parameter_table["image_id"]), scores, failed, "noise", action, f"noise score above {max_score}"
    )


def evaluate_mono_color_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 mono_color_score 生成近单色检查结果。"""
    threshold = _as_float(config.get("threshold", 0.98))
    action = str(config.get("action", "review"))
    scores = cast(pd.Series, pd.to_numeric(parameter_table["mono_color_score"], errors="coerce"))
    failed = cast(pd.Series, scores.notna() & (scores >= threshold))
    return _score_threshold_frame(
        cast(pd.Series, parameter_table["image_id"]),
        scores,
        failed,
        "mono_color",
        action,
        f"mono color score at least {threshold}",
    )


def evaluate_border_padding_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据边框留白比例生成边框检查结果。"""
    max_ratio = _as_float(config.get("max_ratio", 0.25))
    raw_colors = config.get("colors", ["white", "black", "solid"])
    colors = {str(color) for color in raw_colors} if isinstance(raw_colors, (list, tuple, set)) else {str(raw_colors)}
    action = str(config.get("action", "review"))
    ratios = cast(pd.Series, pd.to_numeric(parameter_table["border_padding_ratio"], errors="coerce"))
    sides = parameter_table["border_padding_sides"].fillna("").astype(str)
    border_colors = parameter_table["border_padding_color"].fillna("unknown").astype(str)
    side_counts = sides.map(lambda value: 0 if not value else len(value.split(",")))
    failed = cast(pd.Series, ratios.notna() & (ratios > max_ratio) & (side_counts > 0)
               & border_colors.isin(list(colors)))
    reasons = [
        f"border padding ratio above {max_ratio} sides={side_value} color={color_value}" if failed_value else ""
        for side_value, color_value, failed_value in zip(
            sides.tolist(), border_colors.tolist(), failed.tolist(), strict=True
        )
    ]
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "border_padding_ratio": ratios,
            "border_padding_sides": sides,
            "border_padding_color": border_colors,
            "border_padding_action": failed.map(lambda value: action if value else "keep"),
            "border_padding_reason": reasons,
        }
    )


def evaluate_animated_image_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 animated 标记生成多帧图片检查结果。"""
    action = str(config.get("action", "review"))
    frame_count = cast(pd.Series, pd.to_numeric(parameter_table["frame_count"], errors="coerce"))
    animated = parameter_table["animated"].fillna(False).astype(bool)
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "frame_count": frame_count,
            "animated": animated,
            "animated_action": animated.map(lambda value: action if value else "keep"),
            "animated_reason": animated.map(lambda value: "animated image" if value else ""),
        }
    )


def evaluate_orientation_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据 EXIF orientation 风险生成方向检查结果。"""
    action = str(config.get("action", "review"))
    orientations = cast(pd.Series, pd.to_numeric(parameter_table["exif_orientation"], errors="coerce"))
    risk = parameter_table["orientation_risk"].fillna(False).astype(bool)
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "exif_orientation": orientations,
            "orientation_risk": risk,
            "orientation_action": risk.map(lambda value: action if value else "keep"),
            "orientation_reason": [
                f"exif orientation {int(orientation)}" if risk_value and pd.notna(orientation) else ""
                for orientation, risk_value in zip(orientations.tolist(), risk.tolist(), strict=True)
            ],
        }
    )


def evaluate_exact_duplicate_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据完全重复组生成去重结果。"""
    keep = str(config.get("keep", "first"))
    if keep != "first":
        raise ValueError("exact_duplicate only supports keep='first'")
    action = str(config.get("action", "drop"))
    groups = parameter_table["exact_duplicate_group_id"].fillna("").astype(str)
    counts = cast(pd.Series, pd.to_numeric(parameter_table["exact_duplicate_count"],
                     errors="coerce")).fillna(1).astype(int)

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
        raise ValueError("perceptual_duplicate only supports keep='first'")
    action = str(config.get("action", "drop"))
    if action != "drop":
        raise ValueError("perceptual_duplicate only supports action='drop'")

    groups = parameter_table["perceptual_duplicate_group_id"].fillna("").astype(str)
    counts = cast(pd.Series, pd.to_numeric(parameter_table["perceptual_duplicate_count"],
                     errors="coerce")).fillna(1).astype(int)
    distances = cast(pd.Series, pd.to_numeric(parameter_table["perceptual_duplicate_distance"], errors="coerce"))

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


def evaluate_semantic_duplicate_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据语义重复组生成去重结果。"""
    keep = str(config.get("keep", "first"))
    if keep != "first":
        raise ValueError("semantic_duplicate only supports keep='first'")
    action = str(config.get("action", "drop"))
    if action not in {"drop", "review"}:
        raise ValueError("semantic_duplicate only supports action='drop' or action='review'")

    groups = parameter_table["semantic_duplicate_group_id"].fillna("").astype(str)
    counts = cast(pd.Series, pd.to_numeric(parameter_table["semantic_duplicate_count"],
                     errors="coerce")).fillna(1).astype(int)
    scores = cast(pd.Series, pd.to_numeric(parameter_table["semantic_duplicate_score"], errors="coerce"))
    nearest_ids = parameter_table["semantic_duplicate_nearest_image_id"].fillna("").astype(str)

    seen_groups: set[str] = set()
    actions: list[str] = []
    reasons: list[str] = []
    for group_id, count, score, nearest_id in zip(
        groups.tolist(),
        counts.tolist(),
        scores.tolist(),
        nearest_ids.tolist(),
        strict=True,
    ):
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
        reasons.append(f"semantic duplicate in group {group_id} score {float(score):.4f} nearest {nearest_id}")

    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "semantic_duplicate_group_id": groups,
            "semantic_duplicate_count": counts,
            "semantic_duplicate_score": scores,
            "semantic_duplicate_nearest_image_id": nearest_ids,
            "semantic_duplicate_action": actions,
            "semantic_duplicate_reason": reasons,
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


def _exposure_reason(
    dark: float,
    bright: float,
    clipped: float,
    max_dark: float,
    max_bright: float,
    max_clipped: float,
) -> str:
    """构造曝光检查命中的原因。"""
    reasons: list[str] = []
    if pd.notna(dark) and dark > max_dark:
        reasons.append(f"dark pixel ratio above {max_dark}")
    if pd.notna(bright) and bright > max_bright:
        reasons.append(f"bright pixel ratio above {max_bright}")
    if pd.notna(clipped) and clipped > max_clipped:
        reasons.append(f"clipped pixel ratio above {max_clipped}")
    return "; ".join(reasons)
