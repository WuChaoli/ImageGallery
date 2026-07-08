from pathlib import Path

from examples.generate_light_quality_operator_previews import OPERATOR_PREVIEW_CASES, generate_previews


def test_generate_light_quality_operator_previews_writes_each_operator_html(tmp_path: Path) -> None:
    preview_paths = generate_previews(tmp_path / "operator_previews")

    assert sorted(preview_paths) == sorted(case.operator_name for case in OPERATOR_PREVIEW_CASES)
    for case in OPERATOR_PREVIEW_CASES:
        preview_path = preview_paths[case.operator_name]
        html = preview_path.read_text(encoding="utf-8")
        assert preview_path.exists()
        assert "trigger" in html
        assert case.action_column in html
        assert "review" in html
