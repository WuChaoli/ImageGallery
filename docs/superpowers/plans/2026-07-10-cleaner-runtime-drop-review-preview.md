# Cleaner Runtime Drop Review Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让真实运行 Notebook 为每个逻辑算子导出仅包含 `drop` 和 `review` 结果的 HTML，并给出可核验的命中统计。

**Architecture:** 保持 `CleanerResult.preview_html()` 实现不变，只修正 Notebook 的调用参数与结果校验。Notebook 从导出的 evaluation table 读取每个算子的 action 列，计算期望命中数，并校验 HTML 摘要行数。

**Tech Stack:** Python 3.10、Jupyter Notebook、pandas、pytest

## Global Constraints

- 只修改本次 Notebook、对应契约测试和本执行计划。
- 不修改 Cleaner 运行时或逻辑算子实现。
- 运行和测试使用主仓库 `.venv/bin/python`。

---

### Task 1: 修改并验证逐算子风险预览

**Files:**
- Create: `tests/unit/notebooks/test_cleaner_runtime_stategraph_notebook.py`
- Modify: `notebooks/cleaner_runtime_stategraph_real_test.ipynb`

**Interfaces:**
- Consumes: `CleanerResult.preview_html(path, operator_name=..., actions=..., max_rows=...)`
- Produces: 每个算子的 drop/review HTML，以及包含 `drop_count`、`review_count`、`preview_count`、`preview_path` 的 Notebook 汇总表。

- [ ] **Step 1: 编写失败契约测试**

读取 Notebook JSON，断言预览单元使用 `actions=["drop", "review"]`，并包含 action 统计与 HTML 行数校验。

- [ ] **Step 2: 运行测试并确认因旧的 `actions="full"` 失败**

Run: `/home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/notebooks/test_cleaner_runtime_stategraph_notebook.py -q`

Expected: FAIL，指出缺少 drop/review 筛选。

- [ ] **Step 3: 最小修改 Notebook**

把逐算子预览改为 `actions=["drop", "review"]`；从 `evaluation_frame` 找到算子 action 列，统计 drop/review 数量，并读取 HTML 的 `rows` 摘要验证页面数量。

- [ ] **Step 4: 运行契约测试**

Run: `/home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/notebooks/test_cleaner_runtime_stategraph_notebook.py -q`

Expected: PASS。

- [ ] **Step 5: 执行 Notebook 并核验真实输出**

Run: 在 worktree 中用 `nbclient` 执行 `notebooks/cleaner_runtime_stategraph_real_test.ipynb`。

Expected: Notebook 完成；16 个 HTML 存在；每个 HTML 的 rows 等于该算子的 drop+review 数量。
