"""验证 wheel 与 sdist 的元数据、内容和可重建性。"""

from __future__ import annotations

import email
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

_FORBIDDEN_PARTS = {".env", ".git", ".pytest_cache", "__pycache__", "notebooks", "tests", "tools"}
_REQUIRED_METADATA = {"Name": "image-gallery", "Requires-Python": ">=3.10"}


def _forbidden_paths(names: list[str]) -> list[str]:
    """返回不应进入发布制品的路径。"""
    return [name for name in names if _FORBIDDEN_PARTS.intersection(PurePosixPath(name).parts)]


def validate_wheel(path: Path) -> list[str]:
    """检查 wheel 内容与核心元数据。"""
    findings: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        findings.extend(f"wheel contains forbidden path: {name}" for name in _forbidden_paths(names))
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            return [*findings, "wheel must contain exactly one METADATA file"]
        metadata = email.message_from_bytes(archive.read(metadata_names[0]))
    for field, expected in _REQUIRED_METADATA.items():
        if metadata.get(field) != expected:
            findings.append(f"wheel metadata {field} must be {expected!r}")
    if not metadata.get("Version"):
        findings.append("wheel metadata Version is required")
    return findings


def validate_sdist(path: Path) -> list[str]:
    """检查 sdist 内容并拒绝路径穿越成员。"""
    with tarfile.open(path, "r:gz") as archive:
        names = archive.getnames()
    findings = [f"sdist contains forbidden path: {name}" for name in _forbidden_paths(names)]
    findings.extend(
        f"sdist contains unsafe path: {name}"
        for name in names
        if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
    )
    return findings


def rebuild_sdist(path: Path, output_dir: Path) -> int:
    """安全解包 sdist，并在隔离构建环境中重建 wheel。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="image-gallery-sdist-") as temporary:
        root = Path(temporary).resolve()
        with tarfile.open(path, "r:gz") as archive:
            for member in archive.getmembers():
                destination = (root / member.name).resolve()
                if root not in destination.parents and destination != root:
                    print(f"unsafe sdist member: {member.name}", file=sys.stderr)
                    return 1
            archive.extractall(root)  # noqa: S202
        projects = [item for item in root.iterdir() if item.is_dir()]
        if len(projects) != 1:
            print("sdist must contain exactly one project directory", file=sys.stderr)
            return 1
        command = (
            "uv",
            "run",
            "--isolated",
            "--no-project",
            "--with",
            "build",
            "python",
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(output_dir.resolve()),
            str(projects[0]),
        )
        return subprocess.run(command, check=False, text=True).returncode  # noqa: S603


def run(dist_dir: Path) -> int:
    """验证构建目录中唯一的 wheel/sdist 并重建 sdist。"""
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        print("package check requires exactly one wheel and one sdist", file=sys.stderr)
        return 2
    findings = [*validate_wheel(wheels[0]), *validate_sdist(sdists[0])]
    for finding in findings:
        print(finding)
    if findings:
        return 1
    return rebuild_sdist(sdists[0], Path(".tmp/ci-rebuilt"))


def main() -> int:
    """验证默认 CI 构建目录。"""
    return run(Path(".tmp/ci-dist"))


if __name__ == "__main__":
    raise SystemExit(main())
