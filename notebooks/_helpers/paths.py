"""Path helpers for notebook validation flows."""

from __future__ import annotations

import shutil
from pathlib import Path


def get_repo_root() -> Path:
    """Locate the repository root by walking upward until pyproject.toml is found."""
    repo_root = Path.cwd().resolve()
    while repo_root != repo_root.parent and not (repo_root / "pyproject.toml").exists():
        repo_root = repo_root.parent
    if not (repo_root / "pyproject.toml").exists():
        raise RuntimeError("cannot locate repository root from current working directory")
    return repo_root


def get_notebook_library_root(name: str) -> Path:
    """Return the private runtime directory for a notebook validation flow."""
    return get_repo_root() / "notebooks" / ".operators_test_library" / name


def reset_output_dir(path: Path) -> Path:
    """Remove any previous runtime artifacts and recreate the directory."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
