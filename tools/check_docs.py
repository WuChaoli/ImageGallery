"""检查 Markdown 的确定性结构错误和仓库内部链接。"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import unquote

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
_EXPLICIT_ANCHOR = re.compile(r"<(?:a\s+(?:name|id)|[^>]+\sid)=[\"']([^\"']+)[\"']", re.IGNORECASE)
_SKIPPED_PARTS = {".git", ".qoder", ".tmp", ".venv", ".worktrees"}


def _markdown_files(root: Path) -> Iterable[Path]:
    """遍历仓库内受治理的 Markdown 文件。"""
    return (path for path in root.rglob("*.md") if not _SKIPPED_PARTS.intersection(path.relative_to(root).parts))


def _check_links(line: str, path: Path, root: Path, line_number: int) -> list[str]:
    """检查一行中的仓库内部链接。"""
    relative = path.relative_to(root)
    findings: list[str] = []
    for target in _LINK.findall(line):
        target = target.strip().split(maxsplit=1)[0].strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        destination = unquote(target.split("#", maxsplit=1)[0])
        resolved = (path.parent / destination).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            findings.append(f"{relative}:{line_number}: internal link escapes repository: {target}")
            continue
        if not resolved.exists():
            findings.append(f"{relative}:{line_number}: broken internal link: {target}")
    return findings


def check_file(path: Path, root: Path) -> list[str]:
    """返回单个 Markdown 文件的确定性问题。"""
    content = path.read_text(encoding="utf-8")
    relative = path.relative_to(root)
    findings: list[str] = []
    if content and not content.endswith("\n"):
        findings.append(f"{relative}: missing final newline")

    previous_level = 0
    anchors: set[str] = set()
    fence: tuple[str, int] | None = None
    for line_number, line in enumerate(content.splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            marker = stripped[0]
            length = len(stripped) - len(stripped.lstrip(marker))
            if fence is None:
                fence = (marker, length)
            elif marker == fence[0] and length >= fence[1]:
                fence = None
            continue
        if fence is not None:
            continue

        heading = _HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            if previous_level and level > previous_level + 1:
                findings.append(f"{relative}:{line_number}: heading level skips from {previous_level} to {level}")
            previous_level = level

        for anchor in _EXPLICIT_ANCHOR.findall(line):
            if anchor in anchors:
                findings.append(f"{relative}:{line_number}: duplicate explicit anchor '{anchor}'")
            anchors.add(anchor)

        if re.match(r"^ +(?:[-+*]|\d+[.)])\s", line):
            indentation = len(line) - len(line.lstrip(" "))
            if indentation < 2:
                findings.append(f"{relative}:{line_number}: nested list indentation must be at least 2 spaces")

        findings.extend(_check_links(line, path, root, line_number))

    if fence is not None:
        findings.append(f"{relative}: unclosed fenced code block")
    return findings


def run(root: Path) -> int:
    """检查仓库 Markdown，并返回适合 CI 的退出码。"""
    findings = [finding for path in _markdown_files(root) for finding in check_file(path, root)]
    for finding in findings:
        print(finding)
    return 1 if findings else 0


def main() -> int:
    """检查当前仓库或显式传入的仓库根目录。"""
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    return run(root)


if __name__ == "__main__":
    raise SystemExit(main())
