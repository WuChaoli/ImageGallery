"""Reusable operator configurations for notebook validation flows."""

from __future__ import annotations


def get_cleaning_v3_toml_examples() -> dict[str, str]:
    """Return small TOML examples for notebook-facing cleaner configuration docs."""
    return {
        "all": '[select]\ncategories = ["ALL"]\n',
        "quality_duplicate": (
            '[operators]\n'
            'blur = { min_score = 100.0, action = "review" }\n'
            'exact_duplicate = { action = "drop" }\n\n'
            '[runtime]\n'
            "batch_size = 128\n"
        ),
    }


def get_cleaning_v3_result_api_snippet() -> str:
    """Return the notebook snippet that demonstrates the result-based cleaner API."""
    return "\n".join(
        [
            'result = BasicCleaner(configs).run(dataset, progress="auto")',
            'result.preview_html(PREVIEW_DIR / "quality_blur.html", operator_name="blur")',
            'result.export_table("parameter", RUN_OUTPUT_DIR / "parameter_table.parquet")',
            'result.export_table("evaluation", RUN_OUTPUT_DIR / "evaluation_table.parquet")',
        ]
    )


def get_cleaning_v3_first_batch_operator_configs() -> list[dict[str, dict[str, object]]]:
    """Return the first-batch cleaning-v3 operators used by sample_1000 validation."""
    return [
        {"decode": {}},
        {"dimension": {"min_width": 10, "min_height": 10, "action": "review"}},
        {"aspect_ratio": {}},
        {"megapixel": {"min_megapixels": 0.00001}},
        {"blur": {"min_score": 0.0}},
        {"brightness": {}},
        {"contrast": {"min_score": 0.0}},
        {"blank": {}},
        {"exact_duplicate": {}},
        {"perceptual_duplicate": {}},
    ]


def get_cleaning_v3_quality_baseline_operator_configs() -> list[dict[str, dict[str, object]]]:
    """Return low-risk second-batch operators suitable for baseline quality review."""
    return [
        {"exposure": {}},
        {"border_padding": {}},
        {"mono_color": {}},
    ]


def get_cleaning_v3_light_risk_operator_configs() -> list[dict[str, dict[str, object]]]:
    """Return all second-batch light-risk operators for exploratory review."""
    return [
        {"exposure": {}},
        {"border_padding": {}},
        {"noise": {}},
        {"mono_color": {}},
        {"animated": {}},
        {"orientation": {}},
    ]


def get_cleaning_v3_non_semantic_all_operator_configs() -> list[dict[str, dict[str, object]]]:
    """Return all builtin operators that do not require semantic providers."""
    return [
        *get_cleaning_v3_first_batch_operator_configs(),
        *get_cleaning_v3_light_risk_operator_configs(),
    ]
