from pathlib import Path

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
