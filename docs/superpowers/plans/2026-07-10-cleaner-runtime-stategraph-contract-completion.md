# Cleaner Runtime StateGraph Contract Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 在不改变清洗业务语义的前提下，补齐 Cleaner Runtime StateGraph 设计稿中的公共输入、诊断、预览、运行元数据、导出契约和内部持久化契约。

**Architecture:** 先完成不会改变已完成 run 的对外契约（算子输入、预览、dry-run、sample、导出），再把这些语义贯通到 runtime。最后单独执行 SQLite/cache/artifact 的破坏式布局迁移，确保 resume 只信任 SQLite 与已校验 artifact manifest。语义去重 stage 化依赖新 graph/artifact contract，放在持久化迁移之后完成。

**Tech Stack:** Python 3.10、Pandas/Parquet、SQLite、pytest、ruff、mypy、现有 `Dataset`、`OperatorRegistry`、`ParameterComputer`。

## Global Constraints

- 代码、文件名用 English；注释与 docstring 用中文并遵守 Google Python 风格。
- 不新增服务端、分布式调度器或跨 run artifact 复用。
- 用户业务配置继续使用 `list[{operator_name: config}]`；运行策略继续由 `NodePolicy` 和 `operator_policies` 表达。
- 这是允许破坏式重构的分支：移除与设计稿冲突的 YAML 入口、`output_dir` public API 与根目录表布局兼容读取；不保留双轨兼容。
- 不序列化 Dataset、Storage 或任何 secret；运行缓存默认位于 `~/.cache/image_gallery/cleaning/runs/{run_id}`，`CleanerResult` 不公开内部路径。
- 每个任务先写失败测试，再写最小实现；每个任务通过聚焦测试后才进入下一任务。

---

## Scope and sequencing decision

本计划分为两条可独立验收的交付线：

1. **Phase A（任务 1-5）— 用户契约闭环：** 修复 selector/spec 输入、PreviewPolicy、dry-run、sample/label/tags 和 Result API；这些改变直接改善 Notebook 与脚本使用体验。
2. **Phase B（任务 6-8）— 持久化与恢复严格对齐：** 迁移 cache/schema/artifact contract 并拆分 semantic stages；这是破坏性更强的运行时升级，必须在 Phase A 全量回归后开始。

这避免了把“用户能正确配置、理解和导出结果”的问题与“历史 run 能否恢复”的底层迁移混在同一个不可诊断的大改动中。

## File structure

- Modify: `src/image_gallery/cleaning/selection.py` — 归一化 name、selector、`OperatorSpec` 和 `ConfiguredOperatorSpec`，并处理临时 registry 条目。
- Modify: `src/image_gallery/cleaning/basic.py` — 明确 `operators` API；移除 YAML 与 `output_dir` public surface。
- Modify: `src/image_gallery/operators/builtin.py` — 为每一个 builtin `OperatorSpec` 声明完整 PreviewPolicy。
- Modify: `src/image_gallery/cleaning/execution.py` — 真实 dry-run、run option 解析、稳定 sample dataset 投影与默认 cache root。
- Modify: `src/image_gallery/cleaning/runtime.py` — label/tags/sample 的状态写入、tables/manifests layout、progress 事件和 semantic stage 执行。
- Modify: `src/image_gallery/cleaning/graph.py` — artifact/relation 依赖字段、stage nodes、稳定 plan hash。
- Modify: `src/image_gallery/cleaning/runtime_state.py` — 设计稿 SQLite schema 与所有读写方法。
- Modify: `src/image_gallery/cleaning/artifacts.py` — tmp -> validate -> manifest -> committed 提交流程及 relation manifest。
- Modify: `src/image_gallery/cleaning/result.py` — 严格 Result 导出 API、state/summary 元数据和无兼容路径读取。
- Modify: `src/image_gallery/cleaning/toml_config.py`, `pyproject.toml` — 移除 YAML parser 与 `pyyaml` 依赖。
- Modify: `src/image_gallery/operators/computers/semantic.py` — 声明并执行 `read_embeddings/build_index/find_pairs/write_relations` stages。
- Test: `tests/unit/cleaning/test_selection.py`, `test_preview_policy.py`, `test_execution.py`, `test_graph.py`, `test_runtime_state.py`, `test_artifacts.py`, `test_result.py`。
- Test: `tests/unit/operators/test_builtin_specs.py`。
- Test: `tests/integration/cleaning/test_cleaner_runtime_lifecycle.py`, `test_cleaner_runtime_resume.py`, `test_basic_cleaner_semantic_duplicate.py`, `test_basic_cleaner_export.py`。
- Test: `tests/unit/notebooks/test_cleaner_runtime_stategraph_notebook.py` 与真实 sample_1000 Notebook smoke。

## Task 1: 修正 public 输入边界与算子选择

**Files:**
- Modify: `src/image_gallery/cleaning/selection.py`
- Modify: `src/image_gallery/cleaning/basic.py`
- Modify: `src/image_gallery/operators/registry.py`
- Test: `tests/unit/cleaning/test_selection.py`
- Test: `tests/unit/cleaning/test_basic_cleaner.py`

**Consumes:** `OperatorSpec`、`ConfiguredOperatorSpec`、现有 `OperatorRegistry`。

**Produces:** `select_operators(...) -> list[ConfiguredOperatorSpec]` 可接受 `str | list[str | Mapping | OperatorSpec | ConfiguredOperatorSpec]`；同名临时 spec 默认拒绝，`override=True` 才替换。

- [x] **Step 1: 写入失败测试**

```python
def test_select_operators_accepts_operator_spec_and_uses_default_config() -> None:
    configured = select_operators([custom_spec], registry)
    assert configured == [ConfiguredOperatorSpec.from_spec(custom_spec, {}, source="python")]

def test_select_operators_rejects_duplicate_temporary_spec_without_override() -> None:
    with pytest.raises(ValueError, match="already exists"):
        select_operators([registry.get_operator("quality.blur_check")], registry)
```

- [x] **Step 2: 运行聚焦测试，确认当前分别因类型错误和缺少临时注册逻辑失败**

Run: `PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/cleaning/test_selection.py -q`

- [x] **Step 3: 实现最小归一化逻辑**

在 `_normalize_operator_selectors()` 前先分流 `ConfiguredOperatorSpec`，保留其 config/source；对 `OperatorSpec` 构造 `ConfiguredOperatorSpec.from_spec(spec, {}, source="python")`。将临时 spec 登记到一份 compilation-local registry copy；只有显式 `override=True` 时替换同名 registry spec。保持 selector 的 registry 顺序和现有 mapping 覆盖优先级不变。

- [x] **Step 4: 移除不属于设计稿的入口**

删除 `BasicCleaner.from_yaml()`、`CleanerConfig.from_yaml()`、YAML 测试和 `pyyaml` 依赖；移除 `BasicCleaner.__init__` 的 `output_dir`，只允许 `CleanerExecution` 使用系统默认 cache root。更新调用点为 `run_id` 和显式 Result 导出路径。

- [x] **Step 5: 运行验收**

Run: `PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/cleaning/test_selection.py tests/unit/cleaning/test_basic_cleaner.py tests/unit/cleaning/test_toml_config.py -q`

Expected: PASS；YAML 与 `output_dir` 不再是 public API。

## Task 2: 让 PreviewPolicy 成为所有 builtin 的完整默认契约

**Files:**
- Modify: `src/image_gallery/operators/builtin.py`
- Modify: `src/image_gallery/cleaning/preview_policy.py`
- Test: `tests/unit/operators/test_builtin_specs.py`
- Test: `tests/unit/cleaning/test_preview_policy.py`
- Test: `tests/integration/cleaning/test_cleaner_runtime_preview.py`

**Consumes:** 设计稿的 builtin PreviewPolicy 表和 action 词表。

**Produces:** 每一个 builtin spec 的 `preview_policy` 都显式覆盖 default actions、caption、排序或 duplicate group context；显式 preview 参数仍优先。

- [x] **Step 1: 写参数化失败测试**

```python
@pytest.mark.parametrize(("name", "actions", "captions"), [
    ("format.decode_check", ["drop"], ["decode_reason"]),
    ("quality.blur_check", ["drop", "review"], ["blur_score", "blur_reason"]),
    ("duplicate.perceptual_duplicate_check", ["drop", "review"], ["perceptual_duplicate_distance"]),
])
def test_builtin_preview_policy_matches_runtime_contract(name, actions, captions) -> None:
    policy = create_default_registry().get_operator(name).preview_policy
    assert policy.default_actions == actions
    assert policy.caption_columns == captions
```

- [x] **Step 2: 运行测试，确认除 semantic duplicate 外当前策略为空**

Run: `PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/operators/test_builtin_specs.py tests/unit/cleaning/test_preview_policy.py -q`

- [x] **Step 3: 在 builtin 定义处声明策略**

使用一个 name -> `PreviewPolicy` 的私有映射，并在 `_to_builtin_preview_spec()` 中无条件 `replace()`。逐项落实设计稿表：单算子默认非 keep；duplicate 三类带 groupby/context；`quality.blur_check`、`contrast`、`noise`、`blank` 等带规范排序；保留全局 preview 的 `["drop", "review"]` 默认。

- [x] **Step 4: 增加 HTML 行为测试**

验证 `result.preview_html(path, operator_name="quality.blur_check")` 未传 actions 时只包含该算子的 drop/review 行；`actions="full"` 才包含 keep 行；显式 `caption_columns`、`groupby` 覆盖 builtin policy。

- [x] **Step 5: 运行验收**

Run: `PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/operators/test_builtin_specs.py tests/unit/cleaning/test_preview_policy.py tests/integration/cleaning/test_cleaner_runtime_preview.py -q`

Expected: PASS。

## Task 3: 补齐 dry-run、label/tags 与稳定 sample run

**Files:**
- Modify: `src/image_gallery/cleaning/execution.py`
- Modify: `src/image_gallery/cleaning/runtime.py`
- Modify: `src/image_gallery/cleaning/runtime_state.py`
- Modify: `src/image_gallery/dataset/dataset.py`（仅添加运行时所需的内部 frame 投影 helper）
- Test: `tests/unit/cleaning/test_execution.py`
- Test: `tests/integration/cleaning/test_cleaner_runtime_lifecycle.py`
- Test: `tests/integration/cleaning/test_cleaner_runtime_resume.py`

**Consumes:** 编译 graph、Dataset fingerprint、`RunRecord`。

**Produces:** `run(dataset, label=..., tags=..., sample=100 | {"n": ..., "random_state": ...})`；dry-run 返回真实 diagnostics 且 run 在 dry-run errors 时拒绝开始。

- [x] **Step 1: 写失败测试**

```python
def test_dry_run_reports_dataset_schema_error_before_execution() -> None:
    diagnostics = execution.dry_run(dataset_missing_image_uri)
    assert diagnostics.errors == ["dataset.image_uri column is required"]

def test_sample_int_is_stable_and_is_the_actual_runtime_input() -> None:
    first = execution.run(dataset, sample=2)
    second = execution.run(dataset, sample=2)
    assert first.result("quality.blur_check")["image_id"].tolist() == second.result("quality.blur_check")["image_id"].tolist()
    assert len(first.result("quality.blur_check")) == 2
```

- [x] **Step 2: 运行失败测试**

Run: `PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/cleaning/test_execution.py tests/integration/cleaning/test_cleaner_runtime_lifecycle.py tests/integration/cleaning/test_cleaner_runtime_resume.py -q`

- [x] **Step 3: 归一化运行选项并投影 Dataset**

实现 `sample=100` -> `{"n": 100, "random_state": derived_seed}`，其中 seed 是 dataset fingerprint 与 graph plan hash 的 SHA-256 截断整数。显式 mapping 必须只接受正整数 `n` 与整数 `random_state`。使用稳定排序后 `DataFrame.sample(..., random_state=seed)` 写入仅供本 run 使用的 input artifact，再以原 storage 构造 `Dataset`；不得只记录 metadata 而继续全量执行。

- [x] **Step 4: 实现 dry-run 校验**

检查 dataset 至少含 `image_id`、`image_uri`，读取 fingerprint，验证 graph 的 parameter producer、policy capability 和 preview policy 所引用列；输出 `estimated_artifacts`（tables、relations、computer artifacts）和 `preview_policies`。`CleanerExecution.run()` 先调用 diagnostics，errors 非空时抛出一个汇总 `ValueError`，warnings 经 progress/event 输出。

- [x] **Step 5: 贯通人类元数据与 sample 标识**

为 `RunOptions` 增加 `label: str | None`、`tags: list[str]`、`sample_rule`；解析时校验 tags 全为非空字符串。创建 `RunRecord` 时使用这些值而非 `basic-run`/空列表；summary、state、debug bundle 显示 `is_sample`、sample size/rule。resume 继续校验归一化后的 sample rule。

- [x] **Step 6: 运行验收**

Run: `PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/cleaning/test_execution.py tests/integration/cleaning/test_cleaner_runtime_lifecycle.py tests/integration/cleaning/test_cleaner_runtime_resume.py -q`

Expected: PASS；稳定 sample 实际只处理抽样行，SQLite 和 Result 可读到 label/tags/sample。

## Task 4: 收敛 Result 导出与 manifest/relation API

**Files:**
- Modify: `src/image_gallery/cleaning/result.py`
- Modify: `src/image_gallery/cleaning/runtime.py`
- Test: `tests/unit/cleaning/test_result.py`
- Test: `tests/integration/cleaning/test_basic_cleaner_export.py`

**Consumes:** `manifests/execution_plan.json`、`manifests/artifacts.json`、relation artifact。

**Produces:** `export_manifest(kind, path)` 和 `export_relations(relation_name, path)` 是唯一规范 API；移除旧的 `export_relation()` 与“导出所有 relation 目录”的重载语义。

- [x] **Step 1: 写失败测试**

```python
def test_export_manifest_requires_known_kind(result, tmp_path) -> None:
    assert result.export_manifest("execution_plan", tmp_path / "plan.json").exists()
    with pytest.raises(ValueError, match="unsupported manifest kind"):
        result.export_manifest("parameter_manifest", tmp_path / "x.json")

def test_export_relations_exports_one_named_relation(result, tmp_path) -> None:
    path = result.export_relations("semantic_duplicate_pairs", tmp_path / "pairs.parquet")
    assert pd.read_parquet(path).columns.tolist() == EXPECTED_RELATION_COLUMNS
```

- [x] **Step 2: 运行测试，确认旧签名不匹配**

Run: `PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/cleaning/test_result.py tests/integration/cleaning/test_basic_cleaner_export.py -q`

- [x] **Step 3: 写出并导出规范 manifest**

runtime 在 `manifests/` 写 `execution_plan.json`、`artifacts.json`、`parameter_manifest.json`、`operator_outputs.json`；Result 仅允许 `execution_plan` 与 `artifacts` 两个 manifest kind。relation API 按 relation name 复制单个 parquet，所有路径均由用户传入。

- [x] **Step 4: 消除内部路径泄漏**

`export_debug_bundle()` 使用相对 archive name，重写或剔除 manifest 内的绝对 URI；断言 zip 内容不包含 cache root、Storage credential 或 `work_dir` 字段。`state()`/`summary()` 只返回公开 metadata 和节点摘要。

- [x] **Step 5: 运行验收**

Run: `PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/cleaning/test_result.py tests/integration/cleaning/test_basic_cleaner_export.py -q`

Expected: PASS；旧签名不再被测试或调用。

## Task 5: Notebook 与真实数据用户验收

**Files:**
- Modify: `notebooks/cleaner_runtime_stategraph_real_test.ipynb`
- Modify: `tests/unit/notebooks/test_cleaner_runtime_stategraph_notebook.py`
- Test: `tests/unit/notebooks/test_cleaner_runtime_stategraph_notebook.py`

**Consumes:** Phase A 的 `progress="auto"`、sample、Result preview/export API。

**Produces:** Notebook 展示 dry-run diagnostics、label/tags/sample、每算子的 drop/review preview 和规范 manifest/relation 导出。

- [x] **Step 1: 写 notebook 结构断言**

断言 notebook 包含 `execution.dry_run(dataset)`、`sample=...`、`label=`、`tags=`、`actions=["drop", "review"]`、`export_manifest("artifacts", ...)` 以及 `export_relations("perceptual_duplicate_pairs", ...)`。

- [x] **Step 2: 执行 notebook 并检查产物**

Run: `PYTHONPATH=src:. /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/notebooks/test_cleaner_runtime_stategraph_notebook.py -q`

Run: 使用 `nbclient` 以 worktree 的 `.venv` 执行 `notebooks/cleaner_runtime_stategraph_real_test.ipynb`。

Expected: 每个算子独立 HTML；`preview_count == drop_count + review_count`；sample run 的 SQLite metadata/summary 清晰标记。

## Task 6: 严格迁移 cache layout、SQLite schema 与 artifact 状态

**Files:**
- Modify: `src/image_gallery/cleaning/execution.py`
- Modify: `src/image_gallery/cleaning/context.py`
- Modify: `src/image_gallery/cleaning/runtime.py`
- Modify: `src/image_gallery/cleaning/runtime_state.py`
- Modify: `src/image_gallery/cleaning/artifacts.py`
- Modify: `src/image_gallery/cleaning/result.py`
- Test: `tests/unit/cleaning/test_runtime_state.py`
- Test: `tests/unit/cleaning/test_artifacts.py`
- Test: `tests/integration/cleaning/test_cleaner_runtime_resume.py`

**Consumes:** Phase A manifest export contract.

**Produces:** 新 run 只使用 `~/.cache/image_gallery/cleaning/runs/{run_id}`、`tables/`、`manifests/`、`artifacts/{tmp,committed}`；SQLite 完整记录 schema 所列状态。

- [x] **Step 1: 写 schema 与路径失败测试**

```python
def test_new_run_uses_system_cache_layout_and_tables_subdirectory(result) -> None:
    assert result._run_dir().parent == Path.home() / ".cache/image_gallery/cleaning/runs"
    assert (result._run_dir() / "tables/parameter_table.parquet").exists()
    assert not (result._run_dir() / "parameter_table.parquet").exists()

def test_state_schema_records_artifact_uri_status_and_batch_ranges(store) -> None:
    columns = _columns(store, "artifact")
    assert {"uri", "status", "manifest_uri"} <= columns
```

- [x] **Step 2: 运行失败测试**

Run: `PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/cleaning/test_runtime_state.py tests/unit/cleaning/test_artifacts.py tests/integration/cleaning/test_cleaner_runtime_resume.py -q`

- [x] **Step 3: 破坏式重建 layout 与 schema**

移除 `_table_file()` 的 root fallback。`cleaning_run` 增加 `cache_root/started_at/updated_at/finished_at`；`graph_node` 增加 artifact/relation contract 与 `updated_at/error_message`；stage/batch 增加 attempt、artifact、range/error 字段；artifact 增加 `uri/status`。为每次状态变更写 UTC timestamp，读写 dataclass 与 SQL 均同步更新。

- [x] **Step 4: 实现 atomic artifact 提交与恢复验证**

先写 `artifacts/tmp/<artifact_id>`，校验 parquet schema/row count/checksum，写 manifest 和 commit marker，再 `replace()` 至 `committed`，最后事务更新 SQLite status。resume 要验证 SQLite status、manifest、checksum、row_count、commit marker；任一缺失或不符均拒绝复用。

- [x] **Step 5: 运行验收**

Run: `PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/cleaning/test_runtime_state.py tests/unit/cleaning/test_artifacts.py tests/integration/cleaning/test_cleaner_runtime_resume.py -q`

Expected: PASS；不保留 `/tmp/image-gallery-cleaning-runtime` 或根目录表文件兼容读取。

## Task 7: 扩展 graph artifact/relation contract 并拆分 semantic duplicate stages

**Files:**
- Modify: `src/image_gallery/cleaning/graph.py`
- Modify: `src/image_gallery/operators/computers/base.py`
- Modify: `src/image_gallery/operators/computers/semantic.py`
- Modify: `src/image_gallery/cleaning/runtime.py`
- Test: `tests/unit/cleaning/test_graph.py`
- Test: `tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py`
- Test: `tests/integration/cleaning/test_cleaner_runtime_resume.py`

**Consumes:** Phase B artifact manager 和 stage/batch state。

**Produces:** GraphNode 有 parameter/artifact/relation contract；semantic 图固定为 `read_embeddings -> build_index -> find_pairs -> write_relations -> evaluation -> merge`，各 stage 可 checkpoint/resume。

- [x] **Step 1: 写 graph 与 stage 失败测试**

```python
def test_semantic_graph_declares_stage_dependencies_and_artifacts() -> None:
    graph = CleaningStateGraph.compile(semantic_operator, registry)
    assert [node.node_id for node in graph.nodes if node.computer_name == "semantic_duplicate_group_computer"] == [
        "parameter.semantic_duplicate_group_computer.read_embeddings",
        "parameter.semantic_duplicate_group_computer.build_index",
        "parameter.semantic_duplicate_group_computer.find_pairs",
        "parameter.semantic_duplicate_group_computer.write_relations",
    ]

def test_resume_skips_completed_semantic_stages_and_retries_only_failed_stage() -> None:
    result = execution.run(dataset)
    _mark_stage_failed(result.run_id, "parameter.semantic_duplicate_group_computer.find_pairs")
    resumed = execution.resume(dataset=dataset, run_id=result.run_id)
    assert _completed_stage_names(resumed.run_id) == {
        "read_embeddings", "build_index", "find_pairs", "write_relations"
    }
```

- [x] **Step 2: 运行失败测试**

Run: `PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/cleaning/test_graph.py tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py tests/integration/cleaning/test_cleaner_runtime_resume.py -q`

- [x] **Step 3: 声明 stage contract 并编译 node**

为 `ParameterComputer` 添加不可变 stage 描述（name、required/produced artifacts/relations、capability）。`GraphNode` 增加 `required_artifacts`、`produced_artifacts`、`required_relations`、`produced_relations`、`cache_policy`、`artifact_contract`，并将其纳入 `to_frame()`、SQLite record 与 plan hash。

- [x] **Step 4: 把现有 semantic compute 分解为四个纯阶段**

`read_embeddings` 只验证 embedding manifest 并加载输入；`build_index` 只生成 index artifact；`find_pairs` 只计算 group/pairs；`write_relations` 只提交 relation artifact 与参数更新。runtime 按 stage 写 `stage_run` 和 event；恢复时只跳过已验证的 committed stage artifact。

- [x] **Step 5: 运行验收**

Run: `PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/cleaning/test_graph.py tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py tests/integration/cleaning/test_cleaner_runtime_resume.py -q`

Expected: PASS；semantic 的 index 与 relation 分别有 artifact manifest，failed stage 可单独恢复。

## Task 8: 全量门禁与真实 sample_1000 验收

**Files:**
- Modify only when failures prove an implementation defect in Tasks 1-7.

- [x] **Step 1: 快速门禁**

Run:
`PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/cleaning tests/unit/operators tests/unit/notebooks -q`

Run:
`PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m ruff check src tests`

Run:
`PYTHONPATH=src /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m mypy src/image_gallery`

- [x] **Step 2: integration 门禁**

Run:
`PYTHONPATH=src:. /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/integration/cleaning -q`

- [x] **Step 3: 真实数据与视觉验收**

执行 `notebooks/cleaner_runtime_stategraph_real_test.ipynb`，使用 shared `sample_1000` MinIO dataset；检查：每个 operator preview 的 `<figure>` 数与对应 drop+review 计数一致、semantic/perceptual relation 可导出、artifacts manifest 有 checksum/row_count/commit_marker、debug bundle 不含绝对 cache 路径或 secret。

- [x] **Step 4: 检查变更卫生**

Run: `git diff --check`

Expected: 所有命令退出码为 0；若真实环境缺少 MinIO 或模型依赖，记录未运行命令、替代测试和剩余风险，不得声称已完成真实数据验收。

## Plan self-review

- 设计稿的 operator input、PreviewPolicy、dry-run、sample、label/tags、Result API、cache/schema/artifact、semantic stages 和 Notebook 验收均被覆盖。
- YAML 与 `output_dir` 被明确作为与设计稿冲突的额外 surface 移除；没有把它们无声保留为兼容层。
- 任务顺序遵循依赖：用户 API 先于持久化破坏式迁移，artifact contract 先于 semantic stage resume。
- 每项实施任务均给出目标文件、接口产物、失败测试、验证命令和预期结果；没有 TBD/TODO 占位。
