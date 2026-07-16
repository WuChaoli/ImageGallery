"""阻止在项目许可证尚未由用户确认时执行正式发布。"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    """要求 LICENSE 文件与 PEP 621 license 元数据同时存在。"""
    root = Path(".")
    if not (root / "LICENSE").is_file():
        print("release blocked: user-confirmed LICENSE is missing", file=sys.stderr)
        return 1
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    if "license =" not in pyproject:
        print("release blocked: project license metadata is missing", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
