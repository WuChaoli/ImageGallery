from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib

REPO_ROOT = Path(__file__).parents[3]


def test_pytest_registers_and_excludes_slow_tests_by_default() -> None:
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_config = config["tool"]["pytest"]["ini_options"]

    assert pytest_config["addopts"] == '-m "not slow and not dataset_backend"'
    assert any(marker.startswith("dataset_backend:") for marker in pytest_config["markers"])
    assert any(marker.startswith("slow:") for marker in pytest_config["markers"])
    assert any(marker.startswith("real_dataset:") for marker in pytest_config["markers"])


def test_makefile_forwards_default_real_and_all_test_targets() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "uv run python -m tools.ci test\n" in makefile
    assert "uv run python -m tools.ci test-real" in makefile
    assert "uv run python -m tools.ci test-all" in makefile
