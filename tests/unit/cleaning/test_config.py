import pytest

from image_gallery.cleaning.config import hash_config, parse_operator_configs
from image_gallery.cleaning.errors import OperatorConfigError


def test_parse_operator_configs_accepts_single_operator_items() -> None:
    parsed = parse_operator_configs(
        [
            {"quality.demo_check": {"threshold": 80, "action": "drop"}},
            {"size.dimension_check": {}},
        ]
    )

    assert [item.operator_name for item in parsed] == ["quality.demo_check", "size.dimension_check"]
    assert parsed[0].config == {"threshold": 80, "action": "drop"}
    assert parsed[1].config == {}
    assert len(parsed[0].config_hash) == 64


def test_parse_operator_configs_rejects_invalid_shapes() -> None:
    invalid_inputs = [
        [],
        [{"a": {}, "b": {}}],
        [{"": {}}],
        [{"quality.demo_check": None}],
        [{"quality.demo_check": {}}, {"quality.demo_check": {}}],
    ]

    for invalid_input in invalid_inputs:
        with pytest.raises(OperatorConfigError):
            parse_operator_configs(invalid_input)  # type: ignore[arg-type]


def test_hash_config_is_stable_for_key_order() -> None:
    first = hash_config({"threshold": 80, "action": "drop"})
    second = hash_config({"action": "drop", "threshold": 80})
    different = hash_config({"action": "review", "threshold": 80})

    assert first == second
    assert first != different
