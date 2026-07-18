from dataclasses import replace

from image_gallery.cleaning.preview_policy import PreviewPolicy
from image_gallery.operators._builtin_evaluators import (
    evaluate_animated_image_check,
    evaluate_aspect_ratio_check,
    evaluate_blank_image_check,
    evaluate_blur_check,
    evaluate_border_padding_check,
    evaluate_brightness_check,
    evaluate_contrast_check,
    evaluate_decode_check,
    evaluate_dimension_check,
    evaluate_exact_duplicate_check,
    evaluate_exposure_check,
    evaluate_megapixel_check,
    evaluate_mono_color_check,
    evaluate_noise_check,
    evaluate_orientation_check,
    evaluate_perceptual_duplicate_check,
    evaluate_semantic_duplicate_check,
)
from image_gallery.operators.spec import OperatorSpec


def create_builtin_operator_specs() -> list[OperatorSpec]:
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
        "animated": PreviewPolicy(default_actions=["review"], caption_columns=["frame_count", "animated_reason"]),
        "dimension": PreviewPolicy(default_actions=["drop"], caption_columns=["width", "height", "dimension_reason"]),
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
