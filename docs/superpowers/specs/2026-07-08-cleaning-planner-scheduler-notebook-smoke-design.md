# Cleaning Planner Scheduler Notebook Smoke Design

## Goal

升级现有 `notebooks/cleaning_v3_sample_1000_test.ipynb`，用真实 `sample_1000` 数据验证重构后的清洗平台可用。Notebook 的重点是 smoke + 结构验证：确认 `BasicCleaner.compile()`、`BasicCleaner.plan()`、参数调度、算子评估、状态文件和导出产物能够在同一条链路中跑通。

## Scope

- 修改现有 `notebooks/cleaning_v3_sample_1000_test.ipynb`，不新增平行验证 Notebook。
- 继续复用 `notebooks/_helpers` 中的数据集、MinIO storage 和清洗算子配置 helper。
- 从主工作区复制 `sample_1000/raw.parquet` 和 `sample_1000/import_report.json` 到 worktree，供 Notebook 在隔离分支中运行。
- 保留少量统计和样本展示，方便人工确认结果，但不把 Notebook 做成完整数据分析报告。

## Non-goals

- 不重新生成默认 MinIO 数据集。
- 不复制历史 cleaning run 输出。
- 不新增 cleaner 能力或修改清洗算子语义。
- 不把 Notebook 纳入 CI 自动执行。
- 不改 `_helpers` 公共形状，除非运行验证证明必须适配。

## Notebook Flow

1. Bootstrap repo root so the Notebook can run from `notebooks/` or repo root.
2. Import `BasicCleaner` and `_helpers` utilities.
3. Load and validate `sample_1000/raw.parquet`.
4. Load storage-backed `Dataset` and read a few images through MinIO.
5. Build `BasicCleaner(operator_configs)`.
6. Call `cleaner.compile()` and read `cleaner.plan()`.
7. Assert the plan frame has the expected columns:
   - `step_index`
   - `computer_name`
   - `execution_mode`
   - `requested_parameters`
   - `required_parameters`
   - `produced_parameters`
   - `upstream_computers`
8. Assert the plan includes `per_image` and `dataset_aggregate`, confirming the exact duplicate chain crosses execution modes.
9. Run `cleaner.run(dataset, output_dir=RUN_OUTPUT_DIR, overwrite=True)`.
10. Read and validate structured outputs:
    - `parameter_table.parquet`
    - `evaluation_table.parquet`
    - `parameter_manifest.json`
    - `state.json`
11. Show compact summaries:
    - plan frame
    - table shapes
    - final action counts
    - operator state frame
    - selected rows for dropped or duplicate-related results
12. Validate exports for `full`, `clean`, and `dropped`.

## Validation Expectations

The Notebook should fail loudly if any structural contract breaks:

- required raw dataset columns are missing;
- `cleaner.plan()` returns an empty or malformed plan;
- expected execution modes are absent;
- required parameter columns are not produced;
- evaluation output does not contain final action columns;
- state or manifest files are missing;
- export row counts do not match the evaluated final actions.

The Notebook may still show current data-dependent counts, but it should avoid hard-coding fragile exact totals unless those totals come from invariant relationships such as `full == clean + dropped + review + restricted`.

## Data Copy Policy

The worktree does not contain the local sample dataset by default. Implementation should copy only:

- `notebooks/.importers_test_library/default_minio_dataset/sample_1000/raw.parquet`
- `notebooks/.importers_test_library/default_minio_dataset/sample_1000/import_report.json`

from `/home/wuchaoli/codespace/ImageGallery` into the same relative path under `/home/wuchaoli/codespace/ImageGallery/.worktrees/cleaning-planner-scheduler-refactor`.

Old run outputs under `cleaning_sample_1000_*` are intentionally excluded so the smoke Notebook proves the refactored runtime can recreate fresh outputs.

## Success Criteria

- The upgraded Notebook is runnable in the refactor worktree.
- It uses the refactored `compile()` and `plan()` APIs before `run()`.
- It verifies the planner/scheduler/evaluator chain with real `sample_1000` data.
- It writes fresh cleaning outputs under `notebooks/.operators_test_library/cleaning_v3_sample_1000`.
- It keeps the validation concise enough for repeated manual reruns.
