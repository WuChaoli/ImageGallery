# Cleaner Runtime StateGraph Real Test Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 使用 `notebooks/_helpers/datasets.py` 中的默认 MinIO `sample_1000` 真实数据集，对 `2026-07-09-cleaner-runtime-stategraph-design.md` 覆盖的 Cleaner Runtime StateGraph 设计做全量真实验收。

**Architecture:** 测试分三层：快速单元/小集成测试守住 API 和状态语义，真实 `sample_1000` 集成测试验证全量内置非语义算子，Notebook 验证产出可人工审阅的 HTML、manifest、debug bundle 和日志证据。真实数据测试只通过 `load_default_minio_sample_1000_dataset()` 和 `load_default_minio_sample_1000_frame()` 进入，避免重复构造样板数据。

**Tech Stack:** Python 3.10, pytest, pandas, pyarrow parquet, SQLite, MinIO-backed `Dataset`, Jupyter nbconvert, `image_gallery.cleaning.BasicCleaner`.

## Global Constraints

- 真实数据入口必须来自 `notebooks/_helpers/datasets.py` 的 `load_default_minio_sample_1000_dataset()` 或 `load_default_minio_sample_1000_frame()`。
- 测试和 Notebook 验证统一使用 `.venv/bin/python`。
- 不直接把内部 runtime cache 路径作为用户稳定 API；自动化测试可以读取 `result._run_dir()` 做白盒验收，但 Notebook 面向用户的产物必须通过 `CleanerResult` export API。
- 第一轮真实验收以 `get_cleaning_v3_non_semantic_all_operator_configs()` 为主，语义去重单独使用注入 provider 的确定性集成测试，不依赖外部 embedding 服务。
- sample_1000 或 MinIO 不可用时，真实数据 pytest 应 `pytest.skip(...)`，不能伪造真实数据通过。
- 每个测试任务完成后必须运行对应 pytest 或 nbconvert 命令，并记录验证结果。

---

## File Structure

- Create: `tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py`
  - 真实 `sample_1000` 的主验收测试：selector/TOML/dry-run/run/result/export/preview/manifest/SQLite/state graph/resume/rerun。
- Modify: `notebooks/cleaner_runtime_stategraph_real_test.ipynb`
  - 保留为人工可读验收 Notebook，按本计划补齐 checkpoint、manifest、export、preview 和 cleanup 证据。
- Modify: `notebooks/_helpers/cleaning_configs.py`
  - 如缺少真实测试所需的统一 recipe/helper，只添加最小 helper，不改变现有配置语义。
- Create: `docs/testing/cleaner-runtime-stategraph-real-test-checklist.md`
  - 记录全量测试矩阵、命令、预期产物和人工验收项。

## Test Matrix

| 维度 | 覆盖内容 | 验证方式 |
| --- | --- | --- |
| Dataset | `sample_1000` parquet 存在、MinIO 图片可读、fingerprint 稳定 | pytest + frame 行数/列检查 |
| Selector | `ALL`、`QUALITY`、`DUPLICATE`、显式 name 混用、去重、未知 selector | existing unit + real dry-run |
| TOML | selector、`[[operator]]` override、`operator_policies`、错误路径 | integration pytest |
| Compile/Dry-run | graph nodes、policy、preview policy、estimated artifacts | real dry-run assertions |
| StateGraph | parameter/evaluation/merge 节点、依赖排序、plan hash、manifest | SQLite + exported manifest |
| Runtime | progress events、SQLite run/event/node 状态、label/tags/sample_rule | callback capture + SQLite |
| Result API | `status/summary/state/result/explain/preview/preview_html/export/export_table/export_manifest/export_relations/export_debug_bundle/cleanup` | real run assertions |
| Resume | completed resume、partial resume、dataset mismatch、plan mismatch、artifact missing | pytest with run state mutation |
| Rerun | evaluation-only config 变化可复用参数；parameter/policy 变化拒绝 | pytest |
| PreviewPolicy | 各内置算子默认 actions/caption/group/sort；显式参数覆盖 | HTML + dataframe assertions |
| Action 词表 | `clean/drop/review/full` 到 `keep/drop/review` 映射；非法 action 报错 | pytest |
| Non-semantic operators | first batch + light risk 全覆盖 | real `sample_1000` run |
| Semantic operator | 确定性 provider 的 embedding/index/relation/preview/export | existing deterministic integration + one focused addition |

## Task 1: 真实数据前置体检

**Files:**
- Create: `tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py`
- Read-only: `notebooks/_helpers/datasets.py`

**Interfaces:**
- Consumes: `load_default_minio_sample_1000_dataset()`, `load_default_minio_sample_1000_frame()`
- Produces: pytest fixture `sample_1000_dataset() -> Dataset`

- [ ] **Step 1: 添加真实数据 fixture 与 skip 规则**

```python
from collections.abc import Iterator

import pytest

from notebooks._helpers.datasets import (
    load_default_minio_sample_1000_dataset,
    load_default_minio_sample_1000_frame,
)


@pytest.fixture(scope="module")
def sample_1000_dataset():
    try:
        dataset = load_default_minio_sample_1000_dataset()
    except Exception as exc:
        pytest.skip(f"sample_1000 real dataset unavailable: {exc}")
    return dataset
```

- [ ] **Step 2: 验证真实 parquet 和 Dataset 基础契约**

```python
def test_sample_1000_real_dataset_contract(sample_1000_dataset) -> None:
    frame = load_default_minio_sample_1000_frame()
    assert len(frame) == 1000
    assert {"image_id", "image_uri"}.issubset(frame.columns)

    dataset_frame = sample_1000_dataset.to_frame()
    assert len(dataset_frame) == 1000
    assert dataset_frame["image_id"].is_unique
    assert sample_1000_dataset.fingerprint()
```

- [ ] **Step 3: 运行体检测试**

Run: `.venv/bin/python -m pytest tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py::test_sample_1000_real_dataset_contract -q`

Expected: PASS；若本机缺少数据或 MinIO 连接不可用，显示 SKIPPED 且原因明确。

## Task 2: Compile、Dry-run 与 StateGraph 真实验收

**Files:**
- Modify: `tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py`
- Read-only: `notebooks/_helpers/cleaning_configs.py`

**Interfaces:**
- Consumes: `BasicCleaner`, `get_cleaning_v3_non_semantic_all_operator_configs()`
- Produces: StateGraph 结构断言和 dry-run 诊断断言

- [ ] **Step 1: 添加 compile/dry-run 测试**

```python
from image_gallery.cleaning import BasicCleaner
from notebooks._helpers.cleaning_configs import get_cleaning_v3_non_semantic_all_operator_configs


def test_non_semantic_all_compile_and_dry_run_on_sample_1000(sample_1000_dataset) -> None:
    configs = get_cleaning_v3_non_semantic_all_operator_configs()
    expected_operator_names = [next(iter(item.keys())) for item in configs]

    execution = BasicCleaner(configs).compile()
    plan = execution.plan()
    dry_run = execution.dry_run(sample_1000_dataset)

    assert dry_run.errors == []
    assert dry_run.selected_operators == expected_operator_names
    assert set(expected_operator_names).issubset(dry_run.preview_policies)
    assert "tables/parameter_table.parquet" in dry_run.estimated_artifacts
    assert "tables/evaluation_table.parquet" in dry_run.estimated_artifacts

    node_ids = set(plan["node_id"])
    assert "merge.final_action" in node_ids
    assert any(node_id.startswith("parameter.") for node_id in node_ids)
    for operator_name in expected_operator_names:
        assert f"evaluation.{operator_name}" in node_ids
```

- [ ] **Step 2: 验证 selector 入口**

```python
def test_selector_compile_on_sample_1000_dry_run(sample_1000_dataset) -> None:
    execution = BasicCleaner(["QUALITY", "DUPLICATE"]).compile()
    dry_run = execution.dry_run(sample_1000_dataset)

    assert dry_run.errors == []
    assert any(name.startswith("quality.") for name in dry_run.selected_operators)
    assert any(name.startswith("duplicate.") for name in dry_run.selected_operators)
    assert len(dry_run.selected_operators) == len(set(dry_run.selected_operators))
```

- [ ] **Step 3: 运行 compile/dry-run 测试**

Run: `.venv/bin/python -m pytest tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py -q -k "contract or compile or selector"`

Expected: PASS/SKIP；不得出现真实数据可用但 dry-run errors 非空。

## Task 3: 非语义全量真实运行验收

**Files:**
- Modify: `tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py`

**Interfaces:**
- Consumes: `CleanerExecution.run(dataset, progress=callback, label=..., tags=...)`
- Produces: module-scope fixture `non_semantic_real_result`

- [ ] **Step 1: 添加真实运行 fixture**

```python
import pytest


@pytest.fixture(scope="module")
def non_semantic_real_result(sample_1000_dataset):
    events = []
    configs = get_cleaning_v3_non_semantic_all_operator_configs()
    result = BasicCleaner(configs).compile().run(
        sample_1000_dataset,
        progress=events.append,
        label="sample-1000-stategraph-real",
        tags=["sample_1000", "stategraph", "non_semantic_all"],
    )
    return result, events
```

- [ ] **Step 2: 验证运行状态、事件和表规模**

```python
import pandas as pd


def test_non_semantic_real_run_status_events_and_tables(non_semantic_real_result) -> None:
    result, events = non_semantic_real_result

    assert result.status() == "completed"
    assert any(event.event_type == "run_started" for event in events)
    assert any(event.event_type == "run_completed" for event in events)
    assert any(event.node_id == "merge.final_action" for event in events)

    parameter_path = result.export_table("parameter", result._run_dir() / "_test_exports" / "parameter.parquet")
    evaluation_path = result.export_table("evaluation", result._run_dir() / "_test_exports" / "evaluation.parquet")
    parameter_table = pd.read_parquet(parameter_path)
    evaluation_table = pd.read_parquet(evaluation_path)

    assert len(parameter_table) == 1000
    assert len(evaluation_table) == 1000
    assert "final_action" in evaluation_table.columns
    assert set(evaluation_table["final_action"]).issubset({"keep", "drop", "review"})
```

- [ ] **Step 3: 验证全量非语义算子列存在**

```python
def test_non_semantic_real_run_operator_outputs(non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    configs = get_cleaning_v3_non_semantic_all_operator_configs()
    expected_operator_names = [next(iter(item.keys())) for item in configs]

    state = result.state()
    assert list(state["operator_name"]) == expected_operator_names

    for operator_name in expected_operator_names:
        operator_frame = result.result(operator_name)
        assert len(operator_frame) == 1000
        action_columns = [column for column in operator_frame.columns if column.endswith("_action")]
        assert action_columns, operator_name
```

- [ ] **Step 4: 运行真实全量测试**

Run: `.venv/bin/python -m pytest tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py -q -k "non_semantic_real_run"`

Expected: PASS/SKIP；真实数据可用时必须完成 1000 行非语义全量运行。

## Task 4: Result API、导出和 PreviewPolicy 验收

**Files:**
- Modify: `tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py`

**Interfaces:**
- Consumes: `CleanerResult.export`, `export_table`, `export_manifest`, `export_debug_bundle`, `preview_html`, `explain`
- Produces: 用户显式导出产物断言

- [ ] **Step 1: 验证 clean/review/drop/full 导出与 action 词表**

```python
def test_real_result_exports_action_partitions(non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    export_dir = result._run_dir() / "_test_exports" / "partitions"

    full = result.export("full", export_dir / "full.parquet").to_frame()
    clean = result.export("clean", export_dir / "clean.parquet").to_frame()
    review = result.export("review", export_dir / "review.parquet").to_frame()
    dropped = result.export("dropped", export_dir / "dropped.parquet").to_frame()

    assert len(full) == 1000
    assert len(clean) == int((full["final_action"] == "keep").sum())
    assert len(review) == int((full["final_action"] == "review").sum())
    assert len(dropped) == int((full["final_action"] == "drop").sum())
    assert len(full) == len(clean) + len(review) + len(dropped)
```

- [ ] **Step 2: 验证 manifest 和 debug bundle**

```python
import zipfile


def test_real_result_exports_manifests_and_debug_bundle(non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    export_dir = result._run_dir() / "_test_exports" / "debug"

    execution_plan = result.export_manifest("execution_plan", export_dir / "execution_plan.json")
    artifacts = result.export_manifest("artifacts", export_dir / "artifacts.json")
    bundle = result.export_debug_bundle(export_dir / "debug-cleaning-run.zip")

    assert "merge.final_action" in execution_plan.read_text(encoding="utf-8")
    assert artifacts.read_text(encoding="utf-8").startswith("{")
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
    assert "tables/parameter_table.parquet" in names
    assert "tables/evaluation_table.parquet" in names
    assert "state.json" in names
```

- [ ] **Step 3: 验证 preview_html policy 与显式覆盖**

```python
def test_real_result_preview_html_policy_and_overrides(non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    preview_dir = result._run_dir() / "_test_exports" / "previews"

    overall = result.preview_html(preview_dir / "overall.html")
    blur = result.preview_html(preview_dir / "blur.html", operator_name="quality.blur_check")
    full_clean = result.preview_html(
        preview_dir / "clean_full.html",
        actions="clean",
        max_rows=30,
        columns_per_row=5,
    )

    for path in (overall, blur, full_clean):
        html = path.read_text(encoding="utf-8")
        assert "<html" in html.lower()
        assert "image_id" in html
```

- [ ] **Step 4: 验证 explain**

```python
def test_real_result_explain_contains_parameters_and_outputs(non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    full = result.export("full", result._run_dir() / "_test_exports" / "explain" / "full.parquet").to_frame()
    image_id = str(full.iloc[0]["image_id"])

    explanation = result.explain(image_id)

    assert explanation["image_id"] == image_id
    assert explanation["final_action"] in {"keep", "drop", "review"}
    assert "parameters" in explanation
    assert "operator_outputs" in explanation
```

- [ ] **Step 5: 运行 Result API 测试**

Run: `.venv/bin/python -m pytest tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py -q -k "real_result"`

Expected: PASS/SKIP；产物通过 Result API 导出，HTML 文件非空。

## Task 5: SQLite 状态、checkpoint、resume 与 rerun 验收

**Files:**
- Modify: `tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py`
- Cross-check: `tests/integration/cleaning/test_cleaner_runtime_resume.py`
- Cross-check: `tests/integration/cleaning/test_basic_cleaner_rerun.py`

**Interfaces:**
- Consumes: `CleanerExecution.resume`, `CleanerExecution.rerun`
- Produces: 真实数据 completed resume 和 evaluation-only rerun 验收

- [ ] **Step 1: 验证 SQLite run/node/event 记录**

```python
import sqlite3


def test_real_run_sqlite_state_contains_graph_and_events(non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    database_path = result._run_dir() / "run_state.sqlite"
    assert database_path.exists()

    connection = sqlite3.connect(database_path)
    try:
        run_status = connection.execute(
            "SELECT status FROM cleaning_run WHERE run_id = ?",
            (result.run_id,),
        ).fetchone()[0]
        node_count = connection.execute("SELECT COUNT(*) FROM graph_node").fetchone()[0]
        completed_count = connection.execute(
            "SELECT COUNT(*) FROM graph_node WHERE status = 'completed'",
        ).fetchone()[0]
        event_count = connection.execute("SELECT COUNT(*) FROM run_event").fetchone()[0]
    finally:
        connection.close()

    assert run_status == "completed"
    assert node_count > 0
    assert completed_count == node_count
    assert event_count > 0
```

- [ ] **Step 2: 验证 completed resume 复用历史 run**

```python
def test_real_completed_resume_returns_same_run(sample_1000_dataset, non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    execution = BasicCleaner(get_cleaning_v3_non_semantic_all_operator_configs()).compile()

    resumed = execution.resume(dataset=sample_1000_dataset, result=result)

    assert resumed.run_id == result.run_id
    assert resumed.status() == "completed"
```

- [ ] **Step 3: 验证 evaluation-only rerun**

```python
def test_real_evaluation_only_rerun_reuses_parameter_outputs(non_semantic_real_result) -> None:
    result, _events = non_semantic_real_result
    execution = BasicCleaner(get_cleaning_v3_non_semantic_all_operator_configs()).compile()

    rerun_result = execution.rerun(
        result,
        operators=[{"size.dimension_check": {"min_width": 1, "min_height": 1, "action": "review"}}],
    )

    assert rerun_result.status() == "completed"
    assert rerun_result.run_id == result.run_id
```

- [ ] **Step 4: 运行状态恢复测试**

Run: `.venv/bin/python -m pytest tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py tests/integration/cleaning/test_cleaner_runtime_resume.py tests/integration/cleaning/test_basic_cleaner_rerun.py -q -k "resume or rerun or sqlite"`

Expected: PASS/SKIP；小数据故障注入测试必须 PASS，真实数据测试可因数据不可用 SKIP。

## Task 6: TOML 真实配方验收

**Files:**
- Modify: `tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py`
- Optional Modify: `notebooks/_helpers/cleaning_configs.py`

**Interfaces:**
- Consumes: `BasicCleaner.from_toml`
- Produces: 基于真实 sample_1000 的 TOML run

- [ ] **Step 1: 添加 TOML 配方测试**

```python
def test_real_toml_recipe_runs_on_sample_1000(sample_1000_dataset, tmp_path) -> None:
    recipe_path = tmp_path / "cleaner_runtime_non_semantic.toml"
    recipe_path.write_text(
        "\n".join(
            [
                "[cleaner]",
                'operators = ["QUALITY", "DUPLICATE"]',
                "",
                "[[operator]]",
                'name = "quality.blur_check"',
                "min_score = 0.0",
                'action = "review"',
                "",
                "[[operator]]",
                'name = "duplicate.exact_duplicate_check"',
                'action = "drop"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = BasicCleaner.from_toml(recipe_path).run(sample_1000_dataset, label="sample-1000-toml")

    assert result.status() == "completed"
    assert len(result.export("full", tmp_path / "full.parquet").to_frame()) == 1000
```

- [ ] **Step 2: 运行 TOML 真实测试与现有 TOML 错误测试**

Run: `.venv/bin/python -m pytest tests/integration/cleaning/test_cleaner_runtime_toml.py tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py -q -k "toml"`

Expected: PASS/SKIP；错误路径诊断保持现有测试覆盖。

## Task 7: Notebook 全量验收

**Files:**
- Modify: `notebooks/cleaner_runtime_stategraph_real_test.ipynb`
- Create: `docs/testing/cleaner-runtime-stategraph-real-test-checklist.md`

**Interfaces:**
- Consumes: `load_default_minio_sample_1000_dataset()`, `get_cleaning_v3_non_semantic_all_operator_configs()`
- Produces: 可人工检查的 Notebook 输出和 checklist

- [ ] **Step 1: Notebook 必须包含这些章节**

```text
1. Imports and runtime paths
2. Load sample_1000 real MinIO dataset
3. Build TOML recipe and BasicCleaner
4. Compile plan and dry-run diagnostics
5. Run with progress callback
6. Inspect SQLite state and exported manifests
7. Validate parameter/evaluation/action counts
8. Export clean/review/dropped/full datasets
9. Export operator previews and overall preview HTML
10. Resume completed run
11. Evaluation-only rerun
12. Export debug bundle
13. Cleanup policy check
```

- [ ] **Step 2: checklist 文档写入验证命令**

```markdown
# Cleaner Runtime StateGraph Real Test Checklist

## Required Commands

```bash
.venv/bin/python -m pytest tests/unit/cleaning tests/unit/operators -q
.venv/bin/python -m pytest tests/integration/cleaning -q
.venv/bin/python -m pytest tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py -q
.venv/bin/python -m jupyter nbconvert --to notebook --execute notebooks/cleaner_runtime_stategraph_real_test.ipynb --inplace
.venv/bin/python -m ruff check src tests notebooks/_helpers
.venv/bin/python -m mypy src/image_gallery
```

## Required Evidence

- `sample_1000` row count is 1000.
- Runtime status is `completed`.
- SQLite has completed graph nodes and run events.
- Exported `full = clean + review + dropped`.
- `execution_plan.json`, `artifacts.json`, preview HTML, and debug bundle exist.
- Completed resume returns the same run id.
- Evaluation-only rerun completes without recomputing parameter outputs.
```

- [ ] **Step 3: 执行 Notebook**

Run: `.venv/bin/python -m jupyter nbconvert --to notebook --execute notebooks/cleaner_runtime_stategraph_real_test.ipynb --inplace`

Expected: PASS；如果真实数据或 MinIO 不可用，Notebook 应在数据加载章节明确失败，不允许静默伪造成功。

## Task 8: 最终全量回归命令

**Files:**
- No production code change required.

- [ ] **Step 1: 运行清洗相关单元测试**

Run: `.venv/bin/python -m pytest tests/unit/cleaning tests/unit/operators -q`

Expected: PASS。

- [ ] **Step 2: 运行清洗集成测试**

Run: `.venv/bin/python -m pytest tests/integration/cleaning -q`

Expected: PASS；真实数据缺失时仅真实 sample_1000 测试 SKIP。

- [ ] **Step 3: 运行真实数据专项测试**

Run: `.venv/bin/python -m pytest tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py -q`

Expected: PASS/SKIP；若 `datasets/sample_1000/raw.parquet` 和 MinIO 可用，必须 PASS。

- [ ] **Step 4: 运行静态检查**

Run: `.venv/bin/python -m ruff check src tests notebooks/_helpers`

Expected: PASS。

Run: `.venv/bin/python -m mypy src/image_gallery`

Expected: PASS。

## Acceptance Criteria

- [ ] `BasicCleaner(...).compile().dry_run(sample_1000)` 无 errors，能列出所有非语义内置算子、graph nodes 和 preview policies。
- [ ] `BasicCleaner(get_cleaning_v3_non_semantic_all_operator_configs()).run(sample_1000)` 完成，`result.status() == "completed"`。
- [ ] parameter/evaluation 导出表均为 1000 行，`final_action` 只包含 `keep/drop/review`。
- [ ] `export("full")` 行数等于 `export("clean") + export("review") + export("dropped")` 行数之和。
- [ ] SQLite 中 `cleaning_run.status == completed`，所有 graph node 为 completed，run_event 非空。
- [ ] `export_manifest("execution_plan")` 包含 `merge.final_action`，`export_manifest("artifacts")` 可解析。
- [ ] 每个非语义内置算子 `result.result(operator_name)` 至少包含一个 action column。
- [ ] `preview_html()` 整体预览和 `quality.blur_check` 单算子预览能生成非空 HTML。
- [ ] `result.explain(image_id)` 返回 final action、parameters、operator outputs 和 relation names。
- [ ] completed `resume()` 返回同一 run id 且 completed。
- [ ] evaluation-only `rerun()` 完成；parameter graph/policy 变化拒绝由既有小集成测试覆盖。
- [ ] TOML 配方可以在 sample_1000 上运行完成。
- [ ] Notebook 能执行并留下可人工审阅证据。

## Known Risks

- `result._run_dir()` 是白盒测试入口，不应出现在用户文档示例中；Notebook 面向用户的路径应优先使用显式 export 产物。
- `sample_1000` 真实数据依赖本机 MinIO 和 `datasets/sample_1000/raw.parquet`，CI 若没有该环境应跳过专项测试。
- 语义去重真实外部 provider 成本和稳定性不可控；本计划用确定性 provider 覆盖运行时语义链路，用非语义全量覆盖真实 MinIO 图片读取。
- 当前 runtime 对 partial resume 的真实数据故障注入成本较高，建议继续用现有 `CountingArtifactComputer` 小集成测试覆盖精确“不重复执行已完成参数节点”。

