"""使用固定版本的 OpenSpec CLI 严格校验仓库规范。"""

from __future__ import annotations

import shutil
import subprocess
import sys

OPENSPEC_PACKAGE = "@fission-ai/openspec@1.6.0"


def main() -> int:
    """通过 npm 的跨平台可执行文件运行严格全量校验。"""
    npx = shutil.which("npx.cmd" if sys.platform == "win32" else "npx")
    if npx is None:
        print("npx is required to validate OpenSpec", file=sys.stderr)
        return 2
    command = (npx, "--yes", OPENSPEC_PACKAGE, "validate", "--all", "--strict")
    return subprocess.run(command, check=False, text=True).returncode  # noqa: S603


if __name__ == "__main__":
    raise SystemExit(main())
