from pathlib import Path

import pytest

from image_gallery.cleaning.policy import NodePolicy
from image_gallery.cleaning.toml_config import CleanerConfig


def test_cleaner_config_from_toml_separates_business_and_policy(tmp_path: Path) -> None:
    config_path = tmp_path / "cleaning.toml"
    config_path.write_text(
        """
[operators.blur]
min_score = 120.0
action = "drop"

[operators.blur.runtime]
batch_size = 32

[runtime]
batch_size = 128
""".strip(),
        encoding="utf-8",
    )

    config = CleanerConfig.from_toml(config_path)

    assert config.selectors == ["blur"]
    assert config.operators == ["blur"]
    assert config.operator_configs["blur"] == {"min_score": 120.0, "action": "drop"}
    assert config.node_policy.batch.size == 128
    assert config.operator_policies["blur"].batch.size == 32


def test_cleaner_config_from_toml_defaults_node_policy_when_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "cleaning.toml"
    config_path.write_text(
        """
[select]
categories = ["QUALITY"]
""".strip(),
        encoding="utf-8",
    )

    config = CleanerConfig.from_toml(config_path)

    assert config.selectors == ["QUALITY"]
    assert config.node_policy == NodePolicy()
    assert config.operator_policies == {}


def test_cleaner_config_rejects_select_and_operators_together() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        CleanerConfig.from_mapping(
            {
                "select": {"categories": ["quality"]},
                "operators": {"blur": {}},
            }
        )


def test_cleaner_config_exposes_toml_but_not_yaml_config_entrypoint() -> None:
    assert hasattr(CleanerConfig, "from_toml")
    assert not hasattr(CleanerConfig, "from_yaml")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("checkpoint_enabled", "yes", "enabled must be bool"),
        ("checkpoint_strategy", 1, "strategy must be string"),
        ("device", 1, "device must be string"),
        ("cache_scope", 1, "scope must be string"),
        ("cache_reuse", 1, "reuse must be string"),
        ("cache_cleanup", 1, "cleanup must be string"),
        ("retain_intermediate", "yes", "retain_intermediate must be bool"),
        ("write_debug_manifest", "yes", "write_debug_manifest must be bool"),
        ("fail_fast", "yes", "fail_fast must be bool"),
        ("bad_image_action", 1, "bad_image_action must be string"),
    ],
)
def test_cleaner_config_rejects_runtime_policy_type_mismatches(
    field: str,
    value: object,
    message: str,
) -> None:
    """运行策略字段类型错误必须稳定报告 TypeError。"""
    with pytest.raises(TypeError, match=message):
        CleanerConfig.from_mapping({"runtime": {field: value}})
