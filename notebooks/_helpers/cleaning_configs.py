"""Reusable operator configurations for notebook validation flows."""

from __future__ import annotations


def get_cleaning_v3_toml_examples() -> dict[str, str]:
    """Return small TOML examples for notebook-facing cleaner configuration docs."""
    return {
        "all": '[cleaner]\noperators = ["ALL"]\n',
        "quality_duplicate": (
            '[cleaner]\n'
            'operators = ["QUALITY", "DUPLICATE"]\n\n'
            '[[operator]]\n'
            'name = "quality.blur_check"\n'
            'min_score = 100.0\n'
            'action = "review"\n\n'
            '[[operator]]\n'
            'name = "duplicate.exact_duplicate_check"\n'
            'action = "drop"\n'
        ),
    }


def get_cleaning_v3_result_api_snippet() -> str:
    """Return the notebook snippet that demonstrates the result-based cleaner API."""
    return "\n".join(
        [
            'result = BasicCleaner(configs).run(dataset, progress="auto")',
            'result.preview_html(PREVIEW_DIR / "quality_blur.html", operator_name="quality.blur_check")',
            'result.export_table("parameter", RUN_OUTPUT_DIR / "parameter_table.parquet")',
            'result.export_table("evaluation", RUN_OUTPUT_DIR / "evaluation_table.parquet")',
        ]
    )


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


def get_cleaning_v3_non_semantic_all_operator_configs() -> list[dict[str, dict[str, object]]]:
    """Return all builtin operators that do not require semantic providers."""
    return [
        *get_cleaning_v3_first_batch_operator_configs(),
        *get_cleaning_v3_light_risk_operator_configs(),
    ]
