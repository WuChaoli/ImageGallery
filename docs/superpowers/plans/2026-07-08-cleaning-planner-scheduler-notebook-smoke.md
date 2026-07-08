# Cleaning Planner Scheduler Notebook Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the sample_1000 cleaning Notebook so it smoke-tests the refactored planner, scheduler, evaluator, state, and export flow.

**Architecture:** Keep validation in the existing Notebook and reuse `notebooks/_helpers` for dataset, storage, and operator configs. The Notebook first compiles and inspects the execution plan, then runs `BasicCleaner` on real sample_1000 data and checks persisted outputs. The worktree gets only the raw sample files needed to run the Notebook.

**Tech Stack:** Python 3.10, Jupyter Notebook JSON, pandas, pyarrow, Pillow, MinIO-backed `Dataset`, `BasicCleaner`.

## Global Constraints

- 修改现有 `notebooks/cleaning_v3_sample_1000_test.ipynb`，不新增平行验证 Notebook。
- 继续复用 `notebooks/_helpers` 中的数据集、MinIO storage 和清洗算子配置 helper。
- 只复制 `sample_1000/raw.parquet` 和 `sample_1000/import_report.json` 到 worktree。
- 不复制历史 cleaning run 输出。
- 不重新生成默认 MinIO 数据集。
- 不新增 cleaner 能力或修改清洗算子语义。
- 不把 Notebook 纳入 CI 自动执行。
- 运行和测试统一使用 `.venv/bin/python`。

---

### Task 1: Prepare sample_1000 data in the worktree

**Files:**
- Copy: `/home/wuchaoli/codespace/ImageGallery/notebooks/.importers_test_library/default_minio_dataset/sample_1000/raw.parquet`
- Copy: `/home/wuchaoli/codespace/ImageGallery/notebooks/.importers_test_library/default_minio_dataset/sample_1000/import_report.json`
- Target: `/home/wuchaoli/codespace/ImageGallery/.worktrees/cleaning-planner-scheduler-refactor/notebooks/.importers_test_library/default_minio_dataset/sample_1000/`

**Interfaces:**
- Consumes: existing `_helpers.datasets.get_default_minio_sample_1000_raw_path() -> Path`
- Produces: local worktree dataset files that the Notebook can load without changing helper APIs.

- [ ] **Step 1: Create the target data directory**

Run:

```bash
mkdir -p notebooks/.importers_test_library/default_minio_dataset/sample_1000
```

Expected: directory exists.

- [ ] **Step 2: Copy the two approved data files**

Run:

```bash
cp /home/wuchaoli/codespace/ImageGallery/notebooks/.importers_test_library/default_minio_dataset/sample_1000/raw.parquet \
  notebooks/.importers_test_library/default_minio_dataset/sample_1000/raw.parquet
cp /home/wuchaoli/codespace/ImageGallery/notebooks/.importers_test_library/default_minio_dataset/sample_1000/import_report.json \
  notebooks/.importers_test_library/default_minio_dataset/sample_1000/import_report.json
```

Expected: both files exist in the worktree.

- [ ] **Step 3: Verify the copied dataset is readable**

Run:

```bash
.venv/bin/python - <<'PY'
from notebooks._helpers.datasets import load_default_minio_sample_1000_frame

frame = load_default_minio_sample_1000_frame()
assert len(frame) == 1000
assert {"image_id", "image_uri"}.issubset(frame.columns)
print("sample_1000_rows:", len(frame))
PY
```

Expected: prints `sample_1000_rows: 1000`.

### Task 2: Rewrite the Notebook as planner/scheduler smoke validation

**Files:**
- Modify: `notebooks/cleaning_v3_sample_1000_test.ipynb`

**Interfaces:**
- Consumes:
  - `BasicCleaner.compile() -> BasicCleaner`
  - `BasicCleaner.plan() -> pandas.DataFrame`
  - `BasicCleaner.run(dataset, output_dir, overwrite=True) -> BasicCleaner`
  - `BasicCleaner.state() -> pandas.DataFrame`
  - `BasicCleaner.export(kind: str, path: str) -> Dataset`
- Produces: a runnable Notebook with compact smoke checks for plan, run outputs, state, and exports.

- [ ] **Step 1: Generate the upgraded Notebook JSON**

Run a Python script that writes these cells to `notebooks/cleaning_v3_sample_1000_test.ipynb`:

```python
from __future__ import annotations

import json
from pathlib import Path

path = Path("notebooks/cleaning_v3_sample_1000_test.ipynb")

def markdown(source: str) -> dict[str, object]:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}

def code(source: str) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }

cells = [
    markdown("# Cleaning V3 Sample 1000 Smoke Validation\n\nThis Notebook verifies the refactored cleaning planner, scheduler, evaluator, state, and export flow on the default MinIO `sample_1000` dataset."),
    markdown("## 0. Bootstrap repo root"),
    code("""from __future__ import annotations

import sys
from pathlib import Path

repo_root = Path.cwd().resolve()
while repo_root != repo_root.parent and not (repo_root / "pyproject.toml").exists():
    repo_root = repo_root.parent
if not (repo_root / "pyproject.toml").exists():
    raise RuntimeError("cannot locate repository root")
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

print("repo_root:", repo_root)
"""),
    markdown("## 1. Imports and runtime paths"),
    code("""import json

import pandas as pd

from image_gallery.cleaning import BasicCleaner
from notebooks._helpers.cleaning_configs import get_cleaning_v3_first_batch_operator_configs
from notebooks._helpers.datasets import (
    get_default_minio_sample_1000_raw_path,
    load_default_minio_sample_1000_dataset,
    load_default_minio_sample_1000_frame,
)
from notebooks._helpers.paths import get_notebook_library_root, reset_output_dir

pd.set_option("display.max_columns", 80)

RUN_ROOT = get_notebook_library_root("cleaning_v3_sample_1000")
RUN_OUTPUT_DIR = reset_output_dir(RUN_ROOT / "run")
EXPORT_DIR = reset_output_dir(RUN_ROOT / "exports")

raw_path = get_default_minio_sample_1000_raw_path()
raw_frame = load_default_minio_sample_1000_frame()

print("raw_path:", raw_path)
print("run_output_dir:", RUN_OUTPUT_DIR)
print("export_dir:", EXPORT_DIR)
"""),
    markdown("## 2. Validate raw dataset"),
    code("""required_raw_columns = {"image_id", "image_uri"}
missing_raw_columns = sorted(required_raw_columns.difference(raw_frame.columns))
if missing_raw_columns:
    raise AssertionError(f"missing raw dataset columns: {missing_raw_columns}")
if raw_frame["image_uri"].isna().any():
    raise AssertionError("raw dataset contains empty image_uri values")

print("raw_rows:", len(raw_frame))
print("raw_columns:", raw_frame.columns.tolist())
raw_frame[["image_id", "image_uri"]].head()
"""),
    markdown("## 3. Load storage-backed dataset"),
    code("""dataset = load_default_minio_sample_1000_dataset()

sample_images = []
for image_uri in raw_frame["image_uri"].astype(str).head(3):
    image = dataset.read_image(image_uri)
    sample_images.append(
        {
            "image_uri": image_uri,
            "size": image.size,
            "format": image.format,
        }
    )

pd.DataFrame(sample_images)
"""),
    markdown("## 4. Compile and inspect execution plan"),
    code("""operator_configs = get_cleaning_v3_first_batch_operator_configs()
operator_names = [next(iter(item.keys())) for item in operator_configs]

cleaner = BasicCleaner(operator_configs).compile()
plan_frame = cleaner.plan()

expected_plan_columns = {
    "step_index",
    "computer_name",
    "execution_mode",
    "requested_parameters",
    "required_parameters",
    "produced_parameters",
    "upstream_computers",
}
missing_plan_columns = sorted(expected_plan_columns.difference(plan_frame.columns))
if missing_plan_columns:
    raise AssertionError(f"missing plan columns: {missing_plan_columns}")
if plan_frame.empty:
    raise AssertionError("compiled parameter plan is empty")

execution_modes = set(plan_frame["execution_mode"].astype(str))
required_modes = {"per_image", "dataset_aggregate"}
missing_modes = sorted(required_modes.difference(execution_modes))
if missing_modes:
    raise AssertionError(f"missing execution modes: {missing_modes}")

print("operator_names:", operator_names)
print("execution_modes:", sorted(execution_modes))
plan_frame
"""),
    markdown("## 5. Run BasicCleaner"),
    code("""cleaner.run(dataset, output_dir=RUN_OUTPUT_DIR, overwrite=True)

preview = cleaner.preview(limit=5)
state_frame = cleaner.state()

print("preview:", preview)
state_frame
"""),
    markdown("## 6. Validate persisted outputs"),
    code("""run_dirs = sorted(path for path in RUN_OUTPUT_DIR.iterdir() if path.is_dir())
if len(run_dirs) != 1:
    raise AssertionError(f"expected exactly one run directory, got {run_dirs}")
run_dir = run_dirs[0]

parameter_table_path = run_dir / "parameter_table.parquet"
evaluation_table_path = run_dir / "evaluation_table.parquet"
parameter_manifest_path = run_dir / "parameter_manifest.json"
state_path = run_dir / "state.json"

for output_path in [parameter_table_path, evaluation_table_path, parameter_manifest_path, state_path]:
    if not output_path.exists():
        raise AssertionError(f"missing output file: {output_path}")

parameter_table = pd.read_parquet(parameter_table_path)
evaluation_table = pd.read_parquet(evaluation_table_path)
parameter_manifest = json.loads(parameter_manifest_path.read_text())
state = json.loads(state_path.read_text())

required_parameter_columns = {
    "decode_ok",
    "decode_error",
    "width",
    "height",
    "aspect_ratio",
    "megapixels",
    "blur_score",
    "brightness_score",
    "contrast_score",
    "blank_score",
    "content_hash",
    "exact_duplicate_group_id",
    "exact_duplicate_count",
}
missing_parameter_columns = sorted(required_parameter_columns.difference(parameter_table.columns))
if missing_parameter_columns:
    raise AssertionError(f"missing parameter columns: {missing_parameter_columns}")

required_evaluation_columns = {"image_id", "image_uri", "final_action", "final_reason"}
missing_evaluation_columns = sorted(required_evaluation_columns.difference(evaluation_table.columns))
if missing_evaluation_columns:
    raise AssertionError(f"missing evaluation columns: {missing_evaluation_columns}")

if len(parameter_table) != len(raw_frame):
    raise AssertionError("parameter table row count does not match raw frame")
if len(evaluation_table) != len(raw_frame):
    raise AssertionError("evaluation table row count does not match raw frame")
if state.get("status") != "completed":
    raise AssertionError(f"unexpected cleaner state: {state.get('status')}")

print("run_dir:", run_dir)
print("parameter_table_shape:", parameter_table.shape)
print("evaluation_table_shape:", evaluation_table.shape)
print("manifest_parameters:", sorted(parameter_manifest))
"""),
    markdown("## 7. Summary checks"),
    code("""action_counts = (
    evaluation_table["final_action"]
    .value_counts(dropna=False)
    .rename_axis("final_action")
    .reset_index(name="count")
)

operator_status_counts = (
    state_frame["status"]
    .value_counts(dropna=False)
    .rename_axis("status")
    .reset_index(name="count")
)

display(action_counts)
display(operator_status_counts)
state_frame
"""),
    markdown("## 8. Inspect duplicate or dropped rows"),
    code("""analysis_columns = [
    "image_id",
    "image_uri",
    "final_action",
    "final_reason",
    "exact_duplicate_action",
    "exact_duplicate_reason",
    "exact_duplicate_group_id",
    "exact_duplicate_count",
]
analysis_columns = [column for column in analysis_columns if column in evaluation_table.columns]
analysis_frame = evaluation_table[analysis_columns].copy()

dropped_or_duplicate = analysis_frame.query(
    "final_action != 'keep' or exact_duplicate_count > 1",
    engine="python",
).head(10)

dropped_or_duplicate
"""),
    markdown("## 9. Validate exports"),
    code("""full_export = cleaner.export("full", str(EXPORT_DIR / "full.parquet")).to_frame()
clean_export = cleaner.export("clean", str(EXPORT_DIR / "clean.parquet")).to_frame()
dropped_export = cleaner.export("dropped", str(EXPORT_DIR / "dropped.parquet")).to_frame()

action_counts_map = evaluation_table["final_action"].value_counts(dropna=False).to_dict()
expected_clean_count = int(action_counts_map.get("keep", 0))
expected_dropped_count = int(action_counts_map.get("drop", 0))

if len(full_export) != len(evaluation_table):
    raise AssertionError("full export row count mismatch")
if len(clean_export) != expected_clean_count:
    raise AssertionError("clean export row count mismatch")
if len(dropped_export) != expected_dropped_count:
    raise AssertionError("dropped export row count mismatch")

print("full_export_rows:", len(full_export))
print("clean_export_rows:", len(clean_export))
print("dropped_export_rows:", len(dropped_export))
print("PASS: cleaning v3 planner/scheduler smoke validation completed")
"""),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "pygments_lexer": "ipython3",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n")
```

Expected: Notebook is rewritten with empty outputs and explicit smoke checks.

- [ ] **Step 2: Inspect the Notebook cell outline**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

notebook = json.loads(Path("notebooks/cleaning_v3_sample_1000_test.ipynb").read_text())
for index, cell in enumerate(notebook["cells"]):
    source = "".join(cell.get("source", [])).strip().replace("\n", " ")
    print(f"{index:02d} {cell['cell_type']}: {source[:120]}")
PY
```

Expected: cells include compile/plan, run, persisted output validation, summary, duplicate/dropped inspection, and export validation sections.

### Task 3: Execute and verify the upgraded Notebook

**Files:**
- Modify: `notebooks/cleaning_v3_sample_1000_test.ipynb`
- Runtime output: `notebooks/.operators_test_library/cleaning_v3_sample_1000/`

**Interfaces:**
- Consumes: rewritten Notebook from Task 2.
- Produces: executed Notebook outputs and fresh smoke artifacts.

- [ ] **Step 1: Execute the Notebook in-place**

Run:

```bash
.venv/bin/python - <<'PY'
from __future__ import annotations

import ast
import contextlib
import io
import json
import traceback
from pathlib import Path
from typing import Any

notebook_path = Path("notebooks/cleaning_v3_sample_1000_test.ipynb")
notebook = json.loads(notebook_path.read_text())


def display(*objects: object, **_: object) -> None:
    for obj in objects:
        print(repr(obj))


def run_cell(source: str, global_ns: dict[str, Any]) -> list[dict[str, Any]]:
    stdout = io.StringIO()
    outputs: list[dict[str, Any]] = []
    with contextlib.redirect_stdout(stdout):
        tree = ast.parse(source)
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            prefix = ast.Module(body=tree.body[:-1], type_ignores=[])
            suffix = ast.Expression(body=tree.body[-1].value)
            exec(compile(prefix, "<notebook-cell>", "exec"), global_ns)
            result = eval(compile(suffix, "<notebook-cell>", "eval"), global_ns)
            if result is not None:
                display(result)
        else:
            exec(compile(tree, "<notebook-cell>", "exec"), global_ns)
    text = stdout.getvalue()
    if text:
        outputs.append({"name": "stdout", "output_type": "stream", "text": text.splitlines(keepends=True)})
    return outputs


global_ns: dict[str, Any] = {"__name__": "__main__", "display": display}
execution_count = 1
try:
    for cell in notebook["cells"]:
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        cell["execution_count"] = execution_count
        try:
            cell["outputs"] = run_cell(source, global_ns)
        except Exception as exc:
            tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
            cell["outputs"] = [
                {
                    "ename": type(exc).__name__,
                    "evalue": str(exc),
                    "output_type": "error",
                    "traceback": tb,
                }
            ]
            raise
        finally:
            execution_count += 1
finally:
    notebook_path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n")
PY
```

Expected: command exits 0 and the final cell prints `PASS: cleaning v3 planner/scheduler smoke validation completed`.

- [ ] **Step 2: Verify generated cleaning artifacts**

Run:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path

root = Path("notebooks/.operators_test_library/cleaning_v3_sample_1000")
run_root = root / "run"
exports = root / "exports"
run_dirs = sorted(path for path in run_root.iterdir() if path.is_dir())
assert len(run_dirs) == 1, run_dirs
run_dir = run_dirs[0]
for relative in [
    "parameter_table.parquet",
    "evaluation_table.parquet",
    "parameter_manifest.json",
    "state.json",
]:
    assert (run_dir / relative).exists(), relative
for relative in ["full.parquet", "clean.parquet", "dropped.parquet"]:
    assert (exports / relative).exists(), relative
print("verified_run_dir:", run_dir)
PY
```

Expected: prints the generated run directory.

- [ ] **Step 3: Run focused regression tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators tests/unit/cleaning tests/integration/cleaning -q
```

Expected: all tests pass, with existing skips unchanged.

- [ ] **Step 4: Run lint and typing gates**

Run:

```bash
.venv/bin/python -m ruff check src/image_gallery tests/unit/operators tests/unit/cleaning tests/integration/cleaning
.venv/bin/python -m mypy src/image_gallery
```

Expected: both commands pass.

- [ ] **Step 5: Commit the Notebook smoke validation**

Run:

```bash
git add notebooks/cleaning_v3_sample_1000_test.ipynb \
  docs/superpowers/plans/2026-07-08-cleaning-planner-scheduler-notebook-smoke.md
git commit -m "test: add cleaning planner scheduler notebook smoke"
```

Expected: commit includes the plan and upgraded Notebook. Runtime data and generated outputs remain untracked.
