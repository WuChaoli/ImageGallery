"""拒绝没有限定具体规则的 Python 静态检查 suppression。"""

from __future__ import annotations

import sys
import tokenize
from pathlib import Path


def _python_files(paths: list[Path]) -> list[Path]:
    """展开输入路径中的 Python 文件。"""
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(path.rglob("*.py"))
        elif path.suffix == ".py":
            files.append(path)
    return sorted(set(files))


def _violation(comment: str) -> str | None:
    """返回宽泛 suppression 的违规原因。"""
    normalized = comment.strip()
    if normalized == "# noqa" or normalized.startswith("# noqa "):
        return "noqa must specify a specific rule"
    if "type: ignore" in normalized and "type: ignore[" not in normalized:
        return "type ignore must specify a specific rule"
    if "pyright: ignore" in normalized and "pyright: ignore[" not in normalized:
        return "pyright ignore must specify a specific rule"
    if normalized.startswith("# pyright:") and "pyright: ignore[" not in normalized:
        return "file-level pyright suppression is not allowed"
    return None


def check(paths: list[Path]) -> list[str]:
    """检查路径并返回所有 suppression 违规。"""
    violations: list[str] = []
    for path in _python_files(paths):
        with path.open("rb") as source:
            for token in tokenize.tokenize(source.readline):
                if token.type != tokenize.COMMENT:
                    continue
                reason = _violation(token.string)
                if reason is not None:
                    violations.append(f"{path}:{token.start[0]}: {reason}")
    return violations


def main(argv: list[str] | None = None) -> int:
    """检查命令行路径；默认扫描源码、测试和仓库工具。"""
    arguments = sys.argv[1:] if argv is None else argv
    paths = [Path(argument) for argument in arguments] if arguments else [Path("src"), Path("tests"), Path("tools")]
    violations = check(paths)
    for violation in violations:
        print(violation)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
