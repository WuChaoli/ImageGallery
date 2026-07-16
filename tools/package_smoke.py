"""在隔离环境安装并导入最新构建的 wheel。"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _default_runner(argv: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """执行隔离安装命令并透传输出。"""
    # argv 由固定参数与本地构建目录中的 wheel 路径组成，不通过 shell 解释。
    return subprocess.run(argv, check=False, text=True)  # noqa: S603


def run(dist_dir: Path, *, runner: Runner = _default_runner) -> int:
    """选择最新 wheel，在隔离环境安装并导入包。"""
    wheels = sorted(dist_dir.glob("*.whl"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not wheels:
        print(f"no wheel found in {dist_dir}", file=sys.stderr)
        return 2
    command = (
        "uv",
        "run",
        "--isolated",
        "--no-project",
        "--with",
        str(wheels[0]),
        "python",
        "-c",
        "import image_gallery; import image_gallery.annotations; import image_gallery.cleaning; "
        "import image_gallery.dataset; import image_gallery.storage",
    )
    return runner(command).returncode


def main() -> int:
    """验证默认构建目录中的最新 wheel。"""
    return run(Path(".tmp/ci-dist"))


if __name__ == "__main__":
    raise SystemExit(main())
