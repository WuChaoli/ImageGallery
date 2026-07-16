"""验证确定性文档质量门禁。"""

from pathlib import Path

from tools import check_docs


def test_document_check_accepts_chinese_punctuation_and_unlabeled_fence(tmp_path: Path) -> None:
    """中文标点和无语言围栏不得被误报。"""
    document = tmp_path / "README.md"
    document.write_text("# 标题\n\n这是中文，标点合理。\n\n```\ntext\n```\n", encoding="utf-8")

    assert check_docs.run(tmp_path) == 0


def test_document_check_rejects_unclosed_fence_and_broken_internal_link(tmp_path: Path) -> None:
    """未闭合围栏和失效内部链接必须阻断。"""
    document = tmp_path / "README.md"
    document.write_text("# Title\n\n[missing](docs/missing.md)\n\n```python\n", encoding="utf-8")

    assert check_docs.run(tmp_path) == 1


def test_document_check_rejects_heading_skip_duplicate_anchor_and_missing_newline(tmp_path: Path) -> None:
    """标题层级、重复锚点和文件尾换行必须受检查。"""
    document = tmp_path / "README.md"
    document.write_text('# Title\n<a id="same">\n### Repeated\n<a id="same">', encoding="utf-8")

    findings = check_docs.check_file(document, tmp_path)

    assert any("heading level skips" in finding for finding in findings)
    assert any("duplicate explicit anchor" in finding for finding in findings)
    assert any("missing final newline" in finding for finding in findings)
