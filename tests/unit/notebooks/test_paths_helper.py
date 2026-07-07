from pathlib import Path

from notebooks._helpers.paths import (
    get_notebook_library_root,
    get_repo_root,
    reset_output_dir,
)


def test_get_repo_root_finds_pyproject() -> None:
    repo_root = get_repo_root()
    assert (repo_root / "pyproject.toml").exists()


def test_get_notebook_library_root_scopes_under_operators_test_library() -> None:
    library_root = get_notebook_library_root("cleaning_v3_sample_1000")
    assert library_root == (
        get_repo_root() / "notebooks" / ".operators_test_library" / "cleaning_v3_sample_1000"
    )


def test_reset_output_dir_recreates_empty_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    output_dir.mkdir(parents=True)
    nested = output_dir / "stale.txt"
    nested.write_text("stale", encoding="utf-8")

    reset_path = reset_output_dir(output_dir)

    assert reset_path == output_dir
    assert output_dir.exists()
    assert list(output_dir.iterdir()) == []
