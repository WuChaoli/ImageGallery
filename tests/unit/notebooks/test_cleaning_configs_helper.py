from notebooks._helpers.cleaning_configs import (
    get_cleaning_v3_first_batch_operator_configs,
)


def test_get_cleaning_v3_first_batch_operator_configs_returns_expected_order() -> None:
    operator_configs = get_cleaning_v3_first_batch_operator_configs()

    assert [next(iter(item.keys())) for item in operator_configs] == [
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
