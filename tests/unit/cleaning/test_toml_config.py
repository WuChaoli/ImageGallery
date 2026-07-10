from pathlib import Path

from image_gallery.cleaning.policy import NodePolicy
from image_gallery.cleaning.toml_config import CleanerConfig


def test_cleaner_config_from_toml_separates_business_and_policy(tmp_path: Path) -> None:
    config_path = tmp_path / "cleaning.toml"
    config_path.write_text(
        """
[cleaner]
operators = ["QUALITY"]

[node_policy.batch]
size = 128

[[operator]]
name = "quality.blur_check"
min_score = 120.0
action = "drop"

[operator_policies."quality.blur_check".batch]
size = 32
""".strip(),
        encoding="utf-8",
    )

    config = CleanerConfig.from_toml(config_path)

    assert config.operators == ["QUALITY"]
    assert config.operator_configs["quality.blur_check"]["min_score"] == 120.0
    assert config.node_policy.batch.size == 128
    assert config.operator_policies["quality.blur_check"].batch.size == 32


def test_cleaner_config_from_toml_defaults_node_policy_when_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "cleaning.toml"
    config_path.write_text(
        """
[cleaner]
operators = ["QUALITY"]

[[operator]]
name = "quality.blur_check"
""".strip(),
        encoding="utf-8",
    )

    config = CleanerConfig.from_toml(config_path)

    assert config.node_policy == NodePolicy()
    assert config.operator_policies == {}


def test_cleaner_config_exposes_toml_but_not_yaml_config_entrypoint() -> None:
    assert hasattr(CleanerConfig, "from_toml")
    assert not hasattr(CleanerConfig, "from_yaml")
