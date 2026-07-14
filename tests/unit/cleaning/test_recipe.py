import tempfile
from pathlib import Path

import pytest
import yaml

from image_gallery.cleaning.recipe import CleanerRecipe


def _write_recipe(data: dict[str, object], suffix: str = ".yaml") -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8")
    yaml.dump(data, tmp, allow_unicode=True)
    tmp.close()
    return Path(tmp.name)


class TestFromYaml:
    def test_loads_basic_recipe(self) -> None:
        path = _write_recipe(
            {
                "version": 1,
                "run": {"output_dir": "./output", "cache_root": "./.cache"},
                "operators": [{"use": "blur", "rules": {"drop": "[0, 0.3]", "review": "(0.3, 0.6]"}}],
            }
        )
        recipe = CleanerRecipe.from_yaml(path)
        assert recipe.version == 1
        assert recipe.run_defaults["output_dir"] == "./output"
        assert len(recipe.operators) == 1
        assert recipe.operators[0].use == "blur"

    def test_default_version_is_1(self) -> None:
        path = _write_recipe(
            {
                "operators": [{"use": "decode", "action": "drop"}],
            }
        )
        recipe = CleanerRecipe.from_yaml(path)
        assert recipe.version == 1

    def test_rejects_unsupported_version(self) -> None:
        path = _write_recipe({"version": 2, "operators": [{"use": "blur"}]})
        with pytest.raises(ValueError, match="unsupported recipe version"):
            CleanerRecipe.from_yaml(path)

    def test_rejects_empty_operators(self) -> None:
        path = _write_recipe({"version": 1, "operators": []})
        with pytest.raises(ValueError, match="at least one operator"):
            CleanerRecipe.from_yaml(path)

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            CleanerRecipe.from_yaml("/nonexistent/path.yaml")

    def test_operator_missing_use_key(self) -> None:
        path = _write_recipe({"version": 1, "operators": [{"action": "drop"}]})
        with pytest.raises(ValueError, match="'use' key"):
            CleanerRecipe.from_yaml(path)

    def test_multiple_operators(self) -> None:
        path = _write_recipe(
            {
                "version": 1,
                "operators": [
                    {"use": "blur", "rules": {"drop": "[0, 0.3]"}},
                    {"use": "dimension", "drop": {"min_width": 256}},
                    {"use": "decode", "action": "drop"},
                ],
            }
        )
        recipe = CleanerRecipe.from_yaml(path)
        assert len(recipe.operators) == 3

    def test_non_mapping_yaml_root_raises(self) -> None:
        # YAML 根节点为列表而非映射
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.dump([1, 2, 3], tmp)
        tmp.close()
        with pytest.raises(ValueError, match="must be a mapping"):
            CleanerRecipe.from_yaml(tmp.name)

    def test_custom_registry(self) -> None:
        from image_gallery.operators.builtin import create_default_registry

        custom_reg = create_default_registry()
        path = _write_recipe(
            {
                "version": 1,
                "operators": [{"use": "blur", "action": "drop"}],
            }
        )
        recipe = CleanerRecipe.from_yaml(path, registry=custom_reg)
        assert recipe.operators[0].use == "blur"


class TestCompileSelectors:
    def test_rules_mode(self) -> None:
        path = _write_recipe(
            {
                "version": 1,
                "operators": [{"use": "blur", "rules": {"drop": "[0, 0.3]", "review": "(0.3, 0.6]"}}],
            }
        )
        recipe = CleanerRecipe.from_yaml(path)
        selectors = recipe.compile_selectors()
        assert len(selectors) == 1
        assert "blur" in selectors[0]
        config = selectors[0]["blur"]
        assert isinstance(config, dict)
        assert "rules" in config

    def test_absolute_threshold_mode(self) -> None:
        path = _write_recipe(
            {
                "version": 1,
                "operators": [{"use": "dimension", "drop": {"min_width": 256}, "review": {"min_width": 512}}],
            }
        )
        recipe = CleanerRecipe.from_yaml(path)
        selectors = recipe.compile_selectors()
        assert "dimension" in selectors[0]
        config = selectors[0]["dimension"]
        assert isinstance(config, dict)
        assert config.get("drop") == {"min_width": 256}

    def test_boolean_action_mode(self) -> None:
        path = _write_recipe(
            {
                "version": 1,
                "operators": [{"use": "decode", "action": "drop"}],
            }
        )
        recipe = CleanerRecipe.from_yaml(path)
        selectors = recipe.compile_selectors()
        assert "decode" in selectors[0]
        config = selectors[0]["decode"]
        assert isinstance(config, dict)
        assert config.get("action") == "drop"

    def test_full_name_passthrough(self) -> None:
        path = _write_recipe(
            {
                "version": 1,
                "operators": [{"use": "blur", "action": "review"}],
            }
        )
        recipe = CleanerRecipe.from_yaml(path)
        selectors = recipe.compile_selectors()
        assert "blur" in selectors[0]

    def test_compile_selectors_with_custom_registry(self) -> None:
        from image_gallery.operators.builtin import create_default_registry

        custom_reg = create_default_registry()
        path = _write_recipe(
            {
                "version": 1,
                "operators": [{"use": "blur", "action": "drop"}],
            }
        )
        recipe = CleanerRecipe.from_yaml(path, registry=custom_reg)
        selectors = recipe.compile_selectors(registry=custom_reg)
        assert "blur" in selectors[0]


class TestFromRecipe:
    def test_basic_cleaner_from_recipe(self) -> None:
        from image_gallery.cleaning.basic import BasicCleaner

        path = _write_recipe(
            {
                "version": 1,
                "operators": [
                    {"use": "decode", "action": "drop"},
                    {"use": "blur", "rules": {"drop": "[0, 0.3]"}},
                ],
            }
        )
        cleaner = BasicCleaner.from_recipe(path)
        # 验证 cleaner 可以编译（不报错）
        execution = cleaner.compile()
        assert execution is not None
