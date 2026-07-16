"""对相对默认分支变更的 Python 文件执行 Ruff，并执行全量类型检查。"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence

from tools.ci import CI_TOOL_PATHS

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
GitRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _default_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """执行检查命令并透传输出。"""
    # argv 由固定命令与 Git 返回的路径元素组成，不通过 shell 解释。
    return subprocess.run(argv, check=False, text=True)  # noqa: S603


def _default_git_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """读取 Git 变更路径并捕获标准输出。"""
    # Git argv 完全由本模块固定，不包含用户拼接的 shell 字符串。
    return subprocess.run(argv, capture_output=True, check=False, text=True)  # noqa: S603


def run(*, runner: Runner = _default_runner, git_runner: GitRunner = _default_git_runner) -> int:
    """检查相对 master 的 Python diff，并始终执行产品类型检查。"""
    git_command = ("git", "diff", "--relative", "--name-only", "--diff-filter=d", "master", "--", "*.py")
    diff = git_runner(git_command)
    if diff.returncode != 0:
        return diff.returncode

    paths = tuple(path for path in diff.stdout.splitlines() if path)
    commands: list[tuple[str, ...]] = []
    if paths:
        commands.append(("uv", "run", "ruff", "check", *paths))
    commands.append(("uv", "run", "pyright", "src/image_gallery", *CI_TOOL_PATHS))

    for command in commands:
        result = runner(command)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
