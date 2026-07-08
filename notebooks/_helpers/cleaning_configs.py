"""Reusable operator configurations for notebook validation flows."""

from __future__ import annotations


def get_cleaning_v3_first_batch_operator_configs() -> list[dict[str, dict[str, object]]]:
    """Return the first-batch cleaning-v3 operators used by sample_1000 validation."""
    return [
        {"format.decode_check": {}},
        {"size.dimension_check": {"min_width": 10, "min_height": 10, "action": "review"}},
        {"size.aspect_ratio_check": {}},
        {"size.megapixel_check": {"min_megapixels": 0.00001}},
        {"quality.blur_check": {"min_score": 0.0}},
        {"quality.brightness_check": {}},
        {"quality.contrast_check": {"min_score": 0.0}},
        {"content.blank_image_check": {}},
        {"duplicate.exact_duplicate_check": {}},
        {"duplicate.perceptual_duplicate_check": {}},
    ]


def get_cleaning_v3_quality_baseline_operator_configs() -> list[dict[str, dict[str, object]]]:
    """Return low-risk second-batch operators suitable for baseline quality review."""
    return [
        {"quality.exposure_check": {}},
        {"content.border_padding_check": {}},
        {"content.mono_color_check": {}},
    ]


def get_cleaning_v3_light_risk_operator_configs() -> list[dict[str, dict[str, object]]]:
    """Return all second-batch light-risk operators for exploratory review."""
    return [
        {"quality.exposure_check": {}},
        {"content.border_padding_check": {}},
        {"quality.noise_check": {}},
        {"content.mono_color_check": {}},
        {"format.animated_image_check": {}},
        {"metadata.orientation_check": {}},
    ]
