"""提供跨平台且可复现的仓库 CI 命令入口。"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from collections.abc import Callable, Sequence

Command = tuple[str, ...]
Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]

PYTHON_PATHS = ("src", "tests", "tools")
CI_TOOL_PATHS = (
    "tools/ci.py",
    "tools/lint_diff.py",
    "tools/package_smoke.py",
    "tools/package_validate.py",
    "tools/build_wheel_sbom.py",
    "tools/check_release_license.py",
    "tools/check_external_links.py",
    "tools/check_security_exceptions.py",
    "tools/check_suppressions.py",
    "tools/check_docs.py",
    "tools/check_openspec.py",
)

_COMMANDS: dict[str, tuple[Command, ...]] = {
    "format": (
        ("uv", "run", "ruff", "check", "--fix", *PYTHON_PATHS),
        ("uv", "run", "ruff", "format", *PYTHON_PATHS),
    ),
    "format-check": (("uv", "run", "ruff", "format", "--check", *PYTHON_PATHS),),
    "lint": (
        ("uv", "run", "ruff", "check", *PYTHON_PATHS),
        ("uv", "run", "python", "tools/check_suppressions.py"),
        ("uv", "run", "pyright", "src/image_gallery", *CI_TOOL_PATHS),
    ),
    "lint-package": (
        ("uv", "run", "ruff", "check", "src", "tools"),
        ("uv", "run", "pyright", "src/image_gallery", *CI_TOOL_PATHS),
    ),
    "lint-tests": (("uv", "run", "ruff", "check", "tests"),),
    "lint-diff": (("uv", "run", "python", "tools/lint_diff.py"),),
    "docs": (
        ("uv", "run", "python", "tools/check_docs.py"),
        ("uv", "run", "codespell", "README.md", "AGENTS.md", "docs", "openspec", "src", "tests", "tools"),
        ("uv", "run", "python", "tools/check_openspec.py"),
    ),
    "test": (
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
    ),
    "test-real": (
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
    "test-all": (
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
            "-o",
            "addopts=",
            "tests/",
        ),
    ),
    "coverage": (
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
    ),
    "security-secrets": (("gitleaks", "git", "--redact", "--no-banner", "."),),
    "security-dependencies": (("uv", "run", "pip-audit", "--progress-spinner", "off"),),
    "security-workflows": (("uv", "run", "zizmor", ".github/workflows"),),
    "security-exceptions": (("uv", "run", "python", "tools/check_security_exceptions.py"),),
    "package": (("uv", "run", "python", "-m", "build", "--outdir", ".tmp/ci-dist"),),
    "package-validate": (("uv", "run", "python", "tools/package_validate.py"),),
    "package-smoke": (("uv", "run", "python", "tools/package_smoke.py"),),
    "sbom": (("uv", "run", "python", "tools/build_wheel_sbom.py"),),
    "release-license": (("uv", "run", "python", "tools/check_release_license.py"),),
}

_COMPOSITES: dict[str, tuple[str, ...]] = {
    "check": ("format-check", "lint", "docs", "test"),
    "security": ("security-exceptions", "security-secrets", "security-dependencies", "security-workflows"),
}


def available_tasks() -> tuple[str, ...]:
    """返回稳定且排序后的任务名称。"""
    return tuple(sorted((*_COMMANDS, *_COMPOSITES)))


def _default_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """直接执行固定 argv，并将工具输出透传到当前终端。"""
    # argv 只能来自模块内任务表，不通过 shell 解释。
    return subprocess.run(argv, check=False, text=True)  # noqa: S603


def _run_task(task: str, runner: Runner) -> int:
    """执行一个基础或组合任务，并在首个失败处停止。"""
    for child in _COMPOSITES.get(task, (task,)):
        result = _run_task(child, runner) if child in _COMPOSITES else _run_commands(child, runner)
        if result != 0:
            return result
    return 0


def _run_commands(task: str, runner: Runner) -> int:
    """按顺序执行基础任务的固定命令。"""
    for command in _commands_for_task(task):
        result = runner(command)
        if result.returncode != 0:
            return result.returncode
    return 0


def _commands_for_task(task: str) -> tuple[Command, ...]:
    """返回任务命令，并安全应用历史测试参数覆盖。"""
    commands = _COMMANDS[task]
    if task not in {"test", "test-real", "test-all"}:
        return commands
    command = commands[0]
    test_file = os.environ.get("TEST_FILE", "tests/")
    extra = tuple(shlex.split(os.environ.get("PYTEST_EXTRA", ""), posix=os.name != "nt"))
    return ((*command[:-1], *extra, test_file),)


def main(argv: Sequence[str] | None = None, *, runner: Runner = _default_runner) -> int:
    """解析任务名并返回与底层工具一致的退出码。"""
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if arguments in {("-h",), ("--help",)}:
        print(f"available tasks: {', '.join(available_tasks())}")
        return 0
    if len(arguments) != 1 or arguments[0] not in available_tasks():
        requested = arguments[0] if arguments else "<missing>"
        print(f"unknown task: {requested}", file=sys.stderr)
        print(f"available tasks: {', '.join(available_tasks())}", file=sys.stderr)
        return 2
    return _run_task(arguments[0], runner)


if __name__ == "__main__":
    raise SystemExit(main())
