import json
from pathlib import Path


def test_real_stategraph_notebook_exports_drop_review_previews() -> None:
    """真实验证 Notebook 应逐算子导出并校验 drop/review 预览。"""
    repo_root = Path(__file__).resolve().parents[3]
    notebook_path = repo_root / "notebooks" / "cleaner_runtime_stategraph_real_test.ipynb"
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"] if cell.get("cell_type") == "code")

    assert "cleaner_runtime_non_semantic_all.toml" in source
    assert "BasicCleaner.from_toml(recipe_path)" in source
    assert "execution.dry_run(dataset)" in source
    assert "sample=1000" in source
    assert 'label="cleaner-runtime-stategraph-real-test"' in source
    assert 'tags=["real", "sample_1000", "stategraph"]' in source
    assert 'actions=["drop", "review"]' in source
    assert 'export_manifest("artifacts"' in source
    assert 'export_manifest("execution_plan"' in source
    assert 'export_relations("perceptual_duplicate_pairs"' in source
    assert "drop_count" in source
    assert "review_count" in source
    assert "preview_count" in source
    assert "HTML preview row count mismatch" in source
    assert 'actions="full"' not in source
    assert "from_yaml" not in source
    assert ".yaml" not in source
