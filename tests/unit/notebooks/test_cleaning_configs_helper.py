from notebooks._helpers.cleaning_configs import (
    get_cleaning_v3_first_batch_operator_configs,
    get_cleaning_v3_light_risk_operator_configs,
    get_cleaning_v3_non_semantic_all_operator_configs,
    get_cleaning_v3_quality_baseline_operator_configs,
    get_cleaning_v3_result_api_snippet,
    get_cleaning_v3_toml_examples,
)


def _operator_names(configs: list[dict[str, dict[str, object]]]) -> list[str]:
    return [next(iter(item.keys())) for item in configs]


def test_get_cleaning_v3_first_batch_operator_configs_returns_expected_order() -> None:
    operator_configs = get_cleaning_v3_first_batch_operator_configs()

    assert _operator_names(operator_configs) == [
        "decode",
        "dimension",
        "aspect_ratio",
        "megapixel",
        "blur",
        "brightness",
        "contrast",
        "blank",
        "exact_duplicate",
        "perceptual_duplicate",
    ]


def test_get_cleaning_v3_first_batch_operator_configs_uses_mapping_shape() -> None:
    for item in get_cleaning_v3_first_batch_operator_configs():
        assert isinstance(item, dict)
        assert len(item) == 1
        config = next(iter(item.values()))
        assert isinstance(config, dict)


def test_quality_baseline_operator_configs_include_low_risk_second_batch() -> None:
    assert _operator_names(get_cleaning_v3_quality_baseline_operator_configs()) == [
        "exposure",
        "border_padding",
        "mono_color",
    ]


def test_light_risk_operator_configs_include_all_second_batch_operators() -> None:
    assert _operator_names(get_cleaning_v3_light_risk_operator_configs()) == [
        "exposure",
        "border_padding",
        "noise",
        "mono_color",
        "animated",
        "orientation",
    ]


def test_non_semantic_all_operator_configs_exclude_semantic_duplicate() -> None:
    operator_names = _operator_names(get_cleaning_v3_non_semantic_all_operator_configs())

    assert "semantic_duplicate" not in operator_names
    assert operator_names == [
        "decode",
        "dimension",
        "aspect_ratio",
        "megapixel",
        "blur",
        "brightness",
        "contrast",
        "blank",
        "exact_duplicate",
        "perceptual_duplicate",
        "exposure",
        "border_padding",
        "noise",
        "mono_color",
        "animated",
        "orientation",
    ]


def test_cleaning_v3_toml_examples_cover_selector_inputs() -> None:
    examples = get_cleaning_v3_toml_examples()

    assert '[select]\ncategories = ["ALL"]' in examples["all"]
    assert "[operators]" in examples["quality_duplicate"]
    assert 'blur = { min_score = 100.0, action = "review" }' in examples["quality_duplicate"]
    assert 'exact_duplicate = { action = "drop" }' in examples["quality_duplicate"]


def test_cleaning_v3_result_api_snippet_uses_result_surface() -> None:
    snippet = get_cleaning_v3_result_api_snippet()

    assert 'result = BasicCleaner(configs).run(dataset, progress="auto")' in snippet
    assert "result.preview_html(" in snippet
    assert 'result.export_table("parameter"' in snippet
