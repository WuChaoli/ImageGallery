"""验证跨平台 Python CI 命令入口。"""

from __future__ import annotations

import os
import subprocess
import tarfile
import zipfile
from collections.abc import Sequence
from pathlib import Path

import pytest
from tools import ci, lint_diff, package_smoke, package_validate


class RecordingRunner:
    """记录固定 argv，并可在指定调用返回失败。"""

    def __init__(self, *, fail_at: int | None = None, returncode: int = 1) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.fail_at = fail_at
        self.returncode = returncode

    def __call__(self, argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        """记录调用并返回预设结果。"""
        self.calls.append(tuple(argv))
        code = self.returncode if self.fail_at == len(self.calls) else 0
        return subprocess.CompletedProcess(argv, code)


def test_available_tasks_are_explicit_and_stable() -> None:
    """入口只暴露设计确认的固定任务。"""
    assert ci.available_tasks() == (
        "check",
        "coverage",
        "docs",
        "format",
        "format-check",
        "lint",
        "lint-diff",
        "lint-package",
        "lint-tests",
        "package",
        "package-smoke",
        "package-validate",
        "release-license",
        "sbom",
        "security",
        "security-dependencies",
        "security-exceptions",
        "security-secrets",
        "security-workflows",
        "test",
        "test-all",
        "test-real",
    )


def test_unknown_task_returns_usage_without_running_command(capsys: pytest.CaptureFixture[str]) -> None:
    """未知任务不得被当作任意外部命令执行。"""
    runner = RecordingRunner()

    result = ci.main(["unknown"], runner=runner)

    assert result == 2
    assert runner.calls == []
    output = capsys.readouterr()
    assert "unknown task" in output.err
    assert "format-check" in output.err


def test_help_lists_tasks_without_running_command(capsys: pytest.CaptureFixture[str]) -> None:
    """帮助必须成功列出任务且不执行外部命令。"""
    runner = RecordingRunner()

    result = ci.main(["--help"], runner=runner)

    assert result == 0
    assert runner.calls == []
    assert "lint-diff" in capsys.readouterr().out


def test_lint_uses_fixed_argv_and_stops_after_first_failure() -> None:
    """lint 必须使用固定参数并透明传播首个失败。"""
    runner = RecordingRunner(fail_at=1, returncode=7)

    result = ci.main(["lint"], runner=runner)

    assert result == 7
    assert runner.calls == [("uv", "run", "ruff", "check", "src", "tests", "tools")]


def test_check_runs_read_only_tasks_in_contract_order() -> None:
    """check 必须按格式、lint、测试顺序执行。"""
    runner = RecordingRunner()

    result = ci.main(["check"], runner=runner)

    assert result == 0
    assert runner.calls == [
        ("uv", "run", "ruff", "format", "--check", "src", "tests", "tools"),
        ("uv", "run", "ruff", "check", "src", "tests", "tools"),
        ("uv", "run", "python", "tools/check_suppressions.py"),
        ("uv", "run", "pyright", "src/image_gallery", *ci.CI_TOOL_PATHS),
        ("uv", "run", "python", "tools/check_docs.py"),
        ("uv", "run", "codespell", "README.md", "AGENTS.md", "docs", "openspec", "src", "tests", "tools"),
        ("uv", "run", "python", "tools/check_openspec.py"),
        (
            "uv",
            "run",
            "pytest",
            "-p",
            "no:randomly",
            "-n",
            "auto",
            "--disable-socket",
            "--allow-unix-socket",
            "tests/",
        ),
    ]


def test_test_task_preserves_makefile_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """兼容层必须保留 TEST_FILE 与 PYTEST_EXTRA 参数。"""
    monkeypatch.setenv("TEST_FILE", "tests/unit/tooling")
    monkeypatch.setenv("PYTEST_EXTRA", "-q --maxfail=1")
    runner = RecordingRunner()

    result = ci.main(["test"], runner=runner)

    assert result == 0
    assert runner.calls == [
        (
            "uv",
            "run",
            "pytest",
            "-p",
            "no:randomly",
            "-n",
            "auto",
            "--disable-socket",
            "--allow-unix-socket",
            "-q",
            "--maxfail=1",
            "tests/unit/tooling",
        ),
    ]


def test_format_is_the_only_quality_task_that_modifies_files() -> None:
    """format 才能执行自动修复，format-check 与 lint 必须只读。"""
    format_runner = RecordingRunner()
    check_runner = RecordingRunner()
    lint_runner = RecordingRunner()

    assert ci.main(["format"], runner=format_runner) == 0
    assert ci.main(["format-check"], runner=check_runner) == 0
    assert ci.main(["lint"], runner=lint_runner) == 0

    assert format_runner.calls == [
        ("uv", "run", "ruff", "check", "--fix", "src", "tests", "tools"),
        ("uv", "run", "ruff", "format", "src", "tests", "tools"),
    ]
    assert check_runner.calls == [("uv", "run", "ruff", "format", "--check", "src", "tests", "tools")]
    assert lint_runner.calls == [
        ("uv", "run", "ruff", "check", "src", "tests", "tools"),
        ("uv", "run", "python", "tools/check_suppressions.py"),
        ("uv", "run", "pyright", "src/image_gallery", *ci.CI_TOOL_PATHS),
    ]


@pytest.mark.parametrize(
    ("task", "expected"),
    [
        (
            "test-real",
            (
                "uv",
                "run",
                "pytest",
                "-p",
                "no:randomly",
                "-n",
                "0",
                "--disable-socket",
                "-o",
                "addopts=",
                "-m",
                "real_dataset",
                "tests/",
            ),
        ),
        ("security-dependencies", ("uv", "run", "pip-audit", "--progress-spinner", "off")),
        ("security-workflows", ("uv", "run", "zizmor", ".github/workflows")),
        ("lint-diff", ("uv", "run", "python", "tools/lint_diff.py")),
        ("package", ("uv", "run", "python", "-m", "build", "--outdir", ".tmp/ci-dist")),
        ("package-smoke", ("uv", "run", "python", "tools/package_smoke.py")),
    ],
)
def test_existing_tasks_have_cross_platform_fixed_commands(task: str, expected: tuple[str, ...]) -> None:
    """迁移后的现有任务不得依赖平台 shell 拼接。"""
    runner = RecordingRunner()

    assert ci.main([task], runner=runner) == 0

    assert runner.calls == [expected]


def test_coverage_enforces_repository_and_diff_thresholds() -> None:
    """覆盖率任务必须同时执行全仓基线与变更行门槛。"""
    runner = RecordingRunner()

    assert ci.main(["coverage"], runner=runner) == 0

    assert runner.calls == [
        (
            "uv",
            "run",
            "pytest",
            "-p",
            "no:randomly",
            "-n",
            "auto",
            "--disable-socket",
            "--allow-unix-socket",
            "--cov=src/image_gallery",
            "--cov-report=term-missing",
            "--cov-report=xml:.tmp/coverage.xml",
            "--cov-fail-under=89",
            "tests/",
        ),
        (
            "uv",
            "run",
            "diff-cover",
            ".tmp/coverage.xml",
            "--compare-branch=origin/master",
            "--fail-under=80",
        ),
    ]


def test_package_smoke_selects_latest_wheel_without_shell(tmp_path: Path) -> None:
    """包 smoke 必须使用 Python 选择最新 wheel。"""
    dist = tmp_path / "dist"
    dist.mkdir()
    old_wheel = dist / "image_gallery-0.0.1-py3-none-any.whl"
    new_wheel = dist / "image_gallery-0.0.2-py3-none-any.whl"
    old_wheel.write_bytes(b"old")
    new_wheel.write_bytes(b"new")
    old_wheel.touch()
    new_wheel.touch()
    old_wheel_mtime = old_wheel.stat().st_mtime - 10
    old_wheel.touch()
    os.utime(old_wheel, (old_wheel_mtime, old_wheel_mtime))
    runner = RecordingRunner()

    result = package_smoke.run(dist, runner=runner)

    assert result == 0
    assert runner.calls == [
        (
            "uv",
            "run",
            "--isolated",
            "--no-project",
            "--with",
            str(new_wheel),
            "python",
            "-c",
            "import image_gallery; import image_gallery.annotations; import image_gallery.cleaning; "
            "import image_gallery.dataset; import image_gallery.storage",
        ),
    ]


def test_package_smoke_fails_when_wheel_is_missing(tmp_path: Path) -> None:
    """没有 wheel 时 package smoke 必须明确失败。"""
    runner = RecordingRunner()

    result = package_smoke.run(tmp_path, runner=runner)

    assert result == 2
    assert runner.calls == []


def test_package_validator_accepts_expected_wheel_metadata(tmp_path: Path) -> None:
    """wheel 必须包含正确元数据且不得夹带仓库内部目录。"""
    wheel = tmp_path / "image_gallery-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("image_gallery/__init__.py", "")
        archive.writestr(
            "image_gallery-0.1.0.dist-info/METADATA",
            "Metadata-Version: 2.1\nName: image-gallery\nVersion: 0.1.0\nRequires-Python: >=3.10\n",
        )

    assert package_validate.validate_wheel(wheel) == []


def test_package_validator_rejects_forbidden_sdist_content(tmp_path: Path) -> None:
    """sdist 不得包含测试、Notebook 或内部 CI 脚本。"""
    source = tmp_path / "tool.py"
    source.write_text("pass\n", encoding="utf-8")
    sdist = tmp_path / "image_gallery-0.1.0.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        archive.add(source, arcname="image_gallery-0.1.0/tools/ci.py")

    findings = package_validate.validate_sdist(sdist)

    assert any("forbidden path" in finding for finding in findings)


def test_lint_diff_passes_changed_python_paths_as_argv() -> None:
    """差异 lint 必须以 argv 传递 Git 返回的 Python 路径。"""
    runner = RecordingRunner()

    def git_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        assert tuple(argv) == ("git", "diff", "--relative", "--name-only", "--diff-filter=d", "master", "--", "*.py")
        return subprocess.CompletedProcess(argv, 0, stdout="src/a.py\ntests/test a.py\n")

    result = lint_diff.run(runner=runner, git_runner=git_runner)

    assert result == 0
    assert runner.calls == [
        ("uv", "run", "ruff", "check", "src/a.py", "tests/test a.py"),
        ("uv", "run", "pyright", "src/image_gallery", *ci.CI_TOOL_PATHS),
    ]


def test_lint_diff_still_runs_pyright_when_no_python_file_changed() -> None:
    """没有 Python diff 时仍需执行全量产品类型检查。"""
    runner = RecordingRunner()

    def git_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, stdout="")

    result = lint_diff.run(runner=runner, git_runner=git_runner)

    assert result == 0
    assert runner.calls == [("uv", "run", "pyright", "src/image_gallery", *ci.CI_TOOL_PATHS)]
