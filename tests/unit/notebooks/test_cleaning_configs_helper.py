from notebooks._helpers.cleaning_configs import (
    get_cleaning_v3_first_batch_operator_configs,
    get_cleaning_v3_light_risk_operator_configs,
    get_cleaning_v3_quality_baseline_operator_configs,
)


def _operator_names(configs: list[dict[str, dict[str, object]]]) -> list[str]:
    return [next(iter(item.keys())) for item in configs]


def test_get_cleaning_v3_first_batch_operator_configs_returns_expected_order() -> None:
    operator_configs = get_cleaning_v3_first_batch_operator_configs()

    assert _operator_names(operator_configs) == [
        "format.decode_check",
        "size.dimension_check",
        "size.aspect_ratio_check",
        "size.megapixel_check",
        "quality.blur_check",
        "quality.brightness_check",
        "quality.contrast_check",
        "content.blank_image_check",
        "duplicate.exact_duplicate_check",
        "duplicate.perceptual_duplicate_check",
    ]


def test_get_cleaning_v3_first_batch_operator_configs_uses_mapping_shape() -> None:
    for item in get_cleaning_v3_first_batch_operator_configs():
        assert isinstance(item, dict)
        assert len(item) == 1
        config = next(iter(item.values()))
        assert isinstance(config, dict)


def test_quality_baseline_operator_configs_include_low_risk_second_batch() -> None:
    assert _operator_names(get_cleaning_v3_quality_baseline_operator_configs()) == [
        "quality.exposure_check",
        "content.border_padding_check",
        "content.mono_color_check",
    ]


def test_light_risk_operator_configs_include_all_second_batch_operators() -> None:
    assert _operator_names(get_cleaning_v3_light_risk_operator_configs()) == [
        "quality.exposure_check",
        "content.border_padding_check",
        "quality.noise_check",
        "content.mono_color_check",
        "format.animated_image_check",
        "metadata.orientation_check",
    ]
