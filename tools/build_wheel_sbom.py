"""从目标 wheel 的隔离安装环境生成 CycloneDX SBOM。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_DEVELOPMENT_TOOLS = {"cyclonedx-bom", "pyright", "pytest", "ruff"}


def run(dist_dir: Path, output: Path) -> int:
    """安装唯一目标 wheel，冻结运行依赖并生成 SBOM。"""
    wheels = sorted(dist_dir.glob("*.whl"))
    if len(wheels) != 1:
        print("SBOM generation requires exactly one wheel", file=sys.stderr)
        return 2
    uv = shutil.which("uv")
    if uv is None:
        print("uv is required to generate the wheel SBOM", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="image-gallery-sbom-") as temporary:
        environment = Path(temporary) / "venv"
        commands = (
            (uv, "venv", str(environment), "--python", "3.10", "--seed"),
            (uv, "pip", "install", "--python", str(environment), str(wheels[0].resolve())),
        )
        for command in commands:
            result = subprocess.run(command, check=False, text=True)  # noqa: S603
            if result.returncode != 0:
                return result.returncode
        freeze = subprocess.run(  # noqa: S603
            (uv, "pip", "freeze", "--python", str(environment)),
            capture_output=True,
            check=False,
            text=True,
        )
        if freeze.returncode != 0:
            return freeze.returncode
        requirements = Path(temporary) / "requirements.txt"
        requirements.write_text(freeze.stdout, encoding="utf-8")
        command = (
            uv,
            "run",
            "cyclonedx-py",
            "requirements",
            str(requirements),
            "--pyproject",
            "pyproject.toml",
            "--mc-type",
            "library",
            "--output-reproducible",
            "--of",
            "JSON",
            "-o",
            str(output),
        )
        result = subprocess.run(command, check=False, text=True)  # noqa: S603
        if result.returncode != 0:
            return result.returncode

    document = json.loads(output.read_text(encoding="utf-8"))
    names = {component["name"].casefold() for component in document.get("components", [])}
    unexpected = sorted(names & _DEVELOPMENT_TOOLS)
    if unexpected:
        print(f"SBOM contains development tools: {', '.join(unexpected)}", file=sys.stderr)
        return 1
    if (
        "image-gallery" not in names
        and document.get("metadata", {}).get("component", {}).get("name") != "image-gallery"
    ):
        print("SBOM does not describe image-gallery", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    """从默认 CI 构建目录生成发布 SBOM。"""
    return run(Path(".tmp/ci-dist"), Path(".tmp/image-gallery.cdx.json"))


if __name__ == "__main__":
    raise SystemExit(main())
