from pathlib import Path

import pytest
from tools import ci

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


def test_python_ci_keeps_default_real_and_all_test_tasks_separate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TEST_FILE", raising=False)
    monkeypatch.delenv("PYTEST_EXTRA", raising=False)

    default = ci._commands_for_task("test")[0]
    real = ci._commands_for_task("test-real")[0]
    all_tests = ci._commands_for_task("test-all")[0]
    dataset_backend = ci._commands_for_task("dataset-backend")[0]

    assert "addopts=" not in default
    assert "-m" not in default
    assert ("-o", "addopts=") == real[real.index("-o") : real.index("-o") + 2]
    assert ("-m", "real_dataset") == real[real.index("-m") : real.index("-m") + 2]
    assert ("-o", "addopts=") == all_tests[all_tests.index("-o") : all_tests.index("-o") + 2]
    assert ("-m", "not dataset_backend") == all_tests[all_tests.index("-m") : all_tests.index("-m") + 2]
    assert ("-o", "addopts=") == dataset_backend[dataset_backend.index("-o") : dataset_backend.index("-o") + 2]
    assert ("-m", "dataset_backend") == dataset_backend[dataset_backend.index("-m") : dataset_backend.index("-m") + 2]
    assert dataset_backend[-1] == "tests/integration/dataset_manager"
