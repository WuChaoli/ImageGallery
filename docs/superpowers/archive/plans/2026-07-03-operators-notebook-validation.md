# Operators Notebook Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `notebooks/operators_builtin_test.ipynb` to validate stage 3 cleaning core and stage 4 built-in operators against both local and MinIO imported raw datasets.

**Architecture:** The notebook is the only new runtime artifact. It reads existing local and MinIO raw Parquet datasets, binds `MinioStorage` to the MinIO `Dataset`, then runs the same `BasicCleaner` operator configuration for both datasets and asserts key stage 3/4 contracts.

**Tech Stack:** Jupyter notebook JSON, Python 3.10, pandas, python-dotenv, ImageGallery `Dataset`, `BasicCleaner`, `MinioStorage`.

---

## File Structure

Create:

```text
notebooks/operators_builtin_test.ipynb
```

Responsibilities:

1. Load `notebooks/.importers_test_library/outputs/raw.parquet`.
2. Load `notebooks/.importers_test_library/minio_outputs/raw.parquet`.
3. Connect to MinIO using `.env`.
4. Bind `MinioStorage` to the MinIO Dataset so Dataset image reading handles `s3://...` objects.
5. Run the same `BasicCleaner` configuration for local and MinIO datasets.
6. Display state, preview, parameter/evaluation tables, and selected operator results.
7. Assert stage 3 and stage 4 validation conditions.
8. Export `full`, `clean`, `review`, `dropped`, `parameters`, and `evaluations` for both local and MinIO runs.

Do not modify:

```text
src/image_gallery/
tests/
examples/
```

## Task 1: Create Notebook Skeleton

**Files:**
- Create: `notebooks/operators_builtin_test.ipynb`

- [ ] **Step 1: Create the notebook with setup, markdown headings, and imports**

Create a notebook containing these top-level sections:

```text
# Operators Built-in Validation
## 1. Environment and paths
## 2. Load local raw Dataset
## 3. Load MinIO raw Dataset with storage-backed image reading
## 4. Run BasicCleaner
## 5. Validate stage 3 cleaning core
## 6. Validate stage 4 built-in operators
## 7. Validate config/rerun
## 8. Export views
## 9. PASS
```

The first code cell must contain:

```python
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from dotenv import load_dotenv

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset
from image_gallery.storage import MinioStorage


repo_root = Path.cwd()
if not (repo_root / "pyproject.toml").exists():
    repo_root = repo_root.parent

LOCAL_RAW_DATASET_PATH = repo_root / "notebooks" / ".importers_test_library" / "outputs" / "raw.parquet"
MINIO_RAW_DATASET_PATH = repo_root / "notebooks" / ".importers_test_library" / "minio_outputs" / "raw.parquet"
LIBRARY_ROOT = repo_root / "notebooks" / ".operators_test_library"
OUTPUT_DIR = LIBRARY_ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOCAL_RAW_DATASET_PATH, MINIO_RAW_DATASET_PATH, OUTPUT_DIR
```

- [ ] **Step 2: Run notebook import cell manually or via a small Python JSON check**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("notebooks/operators_builtin_test.ipynb")
data = json.loads(path.read_text(encoding="utf-8"))
assert data["cells"][0]["cell_type"] == "markdown"
assert "Operators Built-in Validation" in "".join(data["cells"][0]["source"])
assert any("LOCAL_RAW_DATASET_PATH" in "".join(cell.get("source", [])) for cell in data["cells"])
print("notebook skeleton ok")
PY
```

Expected: prints `notebook skeleton ok`.

## Task 2: Add Raw Dataset Loading Cells

**Files:**
- Modify: `notebooks/operators_builtin_test.ipynb`

- [ ] **Step 1: Add local raw Dataset loading cell**

Add a code cell:

```python
def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def require_columns(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise AssertionError(f"{label} missing required columns: {missing}")


require_file(LOCAL_RAW_DATASET_PATH, "local raw dataset")
local_dataset = Dataset.from_path(str(LOCAL_RAW_DATASET_PATH))
local_raw_frame = local_dataset.to_frame()
require_columns(local_raw_frame, ["image_id", "image_uri"], "local raw dataset")

print("local rows:", len(local_raw_frame))
print("local columns:", local_raw_frame.columns.tolist())
local_raw_frame.head()
```

- [ ] **Step 2: Add MinIO raw Dataset loading cell**

Add a code cell:

```python
require_file(MINIO_RAW_DATASET_PATH, "MinIO raw dataset")
minio_raw_dataset = Dataset.from_path(str(MINIO_RAW_DATASET_PATH))
minio_raw_frame = minio_raw_dataset.to_frame()
require_columns(minio_raw_frame, ["image_id", "image_uri"], "MinIO raw dataset")

print("minio rows:", len(minio_raw_frame))
print("minio columns:", minio_raw_frame.columns.tolist())
minio_raw_frame[["image_id", "image_uri"]].head()
```

- [ ] **Step 3: Verify raw Dataset cells can be executed outside Jupyter**

Run:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path

import pandas as pd
from image_gallery.dataset import Dataset

repo_root = Path.cwd()
local_path = repo_root / "notebooks" / ".importers_test_library" / "outputs" / "raw.parquet"
minio_path = repo_root / "notebooks" / ".importers_test_library" / "minio_outputs" / "raw.parquet"

for label, path in [("local", local_path), ("minio", minio_path)]:
    frame = Dataset.from_path(str(path)).to_frame()
    missing = [column for column in ["image_id", "image_uri"] if column not in frame.columns]
    assert not missing, f"{label} missing {missing}"
    assert len(frame) > 0, f"{label} raw dataset should not be empty"
print("raw dataset loading ok")
PY
```

Expected: prints `raw dataset loading ok`.

## Task 3: Add MinIO Materialization Cells

**Files:**
- Modify: `notebooks/operators_builtin_test.ipynb`

- [ ] **Step 1: Add MinIO environment and connection cell**

Add a code cell:

```python
load_dotenv(repo_root / ".env")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


raw_endpoint = require_env("IMAGE_GALLERY_MINIO_ENDPOINT")
access_key = require_env("IMAGE_GALLERY_MINIO_ACCESS_KEY")
secret_key = require_env("IMAGE_GALLERY_MINIO_SECRET_KEY")
bucket = require_env("IMAGE_GALLERY_MINIO_BUCKET")

parsed = urlparse(raw_endpoint)
endpoint = parsed.netloc or raw_endpoint
secure = parsed.scheme == "https"

minio_storage = MinioStorage(storage_name="operator_validation_minio").connect(
    endpoint=endpoint,
    access_key=access_key,
    secret_key=secret_key,
    bucket=bucket,
    secure=secure,
)

print("connected bucket:", minio_storage.bucket)
```

- [ ] **Step 2: Add MinIO Dataset storage binding cell**

Add a code cell:

```python
minio_dataset = Dataset.from_path(str(MINIO_RAW_DATASET_PATH), storage=minio_storage)

sample_uri = str(minio_raw_frame.iloc[0]["image_uri"])
sample_image = minio_dataset.read_image(sample_uri)

print("sample minio image:", sample_uri, sample_image.size, sample_image.format)
minio_dataset.to_frame()[["image_id", "image_uri"]].head()
```

- [ ] **Step 3: Verify MinIO Dataset storage binding works outside Jupyter**

Run:

```bash
.venv/bin/python - <<'PY'
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from image_gallery.dataset import Dataset
from image_gallery.storage import MinioStorage

repo_root = Path.cwd()
load_dotenv(repo_root / ".env")

def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

raw_endpoint = require_env("IMAGE_GALLERY_MINIO_ENDPOINT")
parsed = urlparse(raw_endpoint)
endpoint = parsed.netloc or raw_endpoint
secure = parsed.scheme == "https"
storage = MinioStorage(storage_name="operator_validation_minio_check").connect(
    endpoint=endpoint,
    access_key=require_env("IMAGE_GALLERY_MINIO_ACCESS_KEY"),
    secret_key=require_env("IMAGE_GALLERY_MINIO_SECRET_KEY"),
    bucket=require_env("IMAGE_GALLERY_MINIO_BUCKET"),
    secure=secure,
)
dataset = Dataset.from_path(
    str(repo_root / "notebooks" / ".importers_test_library" / "minio_outputs" / "raw.parquet"),
    storage=storage,
)
frame = dataset.to_frame()
image = dataset.read_image(str(frame.iloc[0]["image_uri"]))
assert image.width > 0
assert image.height > 0
print("minio dataset image reading ok")
PY
```

Expected: prints `minio dataset image reading ok`.

## Task 4: Add Cleaner Execution and Validation Cells

**Files:**
- Modify: `notebooks/operators_builtin_test.ipynb`

- [ ] **Step 1: Add shared operator config and runner cell**

Add a code cell:

```python
OPERATOR_CONFIGS = [
    {"format.decode_check": {}},
    {"size.dimension_check": {"min_width": 1, "min_height": 1, "action": "review"}},
    {"quality.blur_check": {"threshold": 0.0, "action": "review"}},
    {"quality.brightness_check": {"min_threshold": 0.0, "max_threshold": 255.0, "action": "review"}},
    {"quality.contrast_check": {"threshold": 0.0, "action": "review"}},
    {"duplicate.exact_duplicate_check": {"action": "review"}},
]


def run_cleaner(label: str, dataset: Dataset) -> dict[str, object]:
    run_output_dir = OUTPUT_DIR / label
    cleaner = BasicCleaner(OPERATOR_CONFIGS)
    cleaner.run(dataset, output_dir=run_output_dir)
    context = cleaner._context
    if context is None:
        raise AssertionError(f"{label} cleaner context should exist")
    paths = context.paths
    return {
        "label": label,
        "cleaner": cleaner,
        "paths": paths,
        "parameter_table": pd.read_parquet(paths.parameter_table_path),
        "evaluation_table": pd.read_parquet(paths.evaluation_table_path),
        "preview": cleaner.preview(),
        "state": cleaner.state(),
    }


local_result = run_cleaner("local", local_dataset)
minio_result = run_cleaner("minio", minio_dataset)
local_result["state"], minio_result["state"]
```

- [ ] **Step 2: Add stage 3 core assertions cell**

Add a code cell:

```python
def validate_stage3_core(result: dict[str, object]) -> None:
    label = str(result["label"])
    cleaner = result["cleaner"]
    paths = result["paths"]
    preview = result["preview"]
    state = result["state"]

    for path in [
        paths.parameter_table_path,
        paths.evaluation_table_path,
        paths.operator_outputs_path,
        paths.state_path,
    ]:
        if not path.exists():
            raise AssertionError(f"{label} missing output: {path}")

    expected_operators = [next(iter(item.keys())) for item in OPERATOR_CONFIGS]
    if state["operator_name"].tolist() != expected_operators:
        raise AssertionError(f"{label} state operator order mismatch")
    if not {"clean_count", "review_count", "dropped_count", "restricted_count"}.issubset(set(vars(preview))):
        raise AssertionError(f"{label} preview missing count attributes")

    for operator_name in expected_operators:
        result_frame = cleaner.result(operator_name)
        if not {"image_id", "image_uri"}.issubset(result_frame.columns):
            raise AssertionError(f"{label} result missing identity columns for {operator_name}")


validate_stage3_core(local_result)
validate_stage3_core(minio_result)
print("stage3 core validation ok")
```

- [ ] **Step 3: Add stage 4 operator assertions cell**

Add a code cell:

```python
PARAMETER_COLUMNS = [
    "width",
    "height",
    "decode_ok",
    "decode_error",
    "blur_score",
    "brightness_score",
    "contrast_score",
    "content_hash",
    "phash",
    "exact_duplicate_group_id",
]

EVALUATION_COLUMNS = [
    "decode_action",
    "decode_reason",
    "dimension_action",
    "dimension_reason",
    "blur_action",
    "blur_reason",
    "brightness_action",
    "brightness_reason",
    "contrast_action",
    "contrast_reason",
    "exact_duplicate_action",
    "exact_duplicate_reason",
    "final_action",
    "final_reason",
    "triggered_operator_names",
]


def validate_stage4_columns(result: dict[str, object]) -> None:
    label = str(result["label"])
    parameter_table = result["parameter_table"]
    evaluation_table = result["evaluation_table"]
    require_columns(parameter_table, PARAMETER_COLUMNS, f"{label} parameter_table")
    require_columns(evaluation_table, EVALUATION_COLUMNS, f"{label} evaluation_table")


validate_stage4_columns(local_result)
validate_stage4_columns(minio_result)
local_result["parameter_table"].head(), minio_result["parameter_table"].head()
```

- [ ] **Step 4: Verify cleaner validation logic by running equivalent Python script**

Run:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path

import pandas as pd
from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset

repo_root = Path.cwd()
dataset = Dataset.from_path(str(repo_root / "notebooks" / ".importers_test_library" / "outputs" / "raw.parquet"))
output_dir = repo_root / "notebooks" / ".operators_test_library" / "script_check"
cleaner = BasicCleaner([
    {"format.decode_check": {}},
    {"size.dimension_check": {"min_width": 1, "min_height": 1, "action": "review"}},
    {"quality.blur_check": {"threshold": 0.0, "action": "review"}},
    {"quality.brightness_check": {"min_threshold": 0.0, "max_threshold": 255.0, "action": "review"}},
    {"quality.contrast_check": {"threshold": 0.0, "action": "review"}},
    {"duplicate.exact_duplicate_check": {"action": "review"}},
])
cleaner.run(dataset, output_dir=output_dir)
paths = cleaner._context.paths
parameter_table = pd.read_parquet(paths.parameter_table_path)
evaluation_table = pd.read_parquet(paths.evaluation_table_path)
assert "blur_score" in parameter_table.columns
assert "final_action" in evaluation_table.columns
print("cleaner validation prerequisite ok")
PY
```

Expected: prints `cleaner validation prerequisite ok`.

## Task 5: Add config/rerun and Export Cells

**Files:**
- Modify: `notebooks/operators_builtin_test.ipynb`

- [ ] **Step 1: Add config/rerun validation cell**

Add a code cell:

```python
local_cleaner = local_result["cleaner"]
local_cleaner.config([{"quality.blur_check": {"threshold": 999999.0, "action": "review"}}])
stale_state = local_cleaner.state()
if stale_state.loc[stale_state["operator_name"] == "quality.blur_check", "status"].item() != "stale":
    raise AssertionError("quality.blur_check should be stale after config()")

local_cleaner.rerun([{"quality.blur_check": {"threshold": 999999.0, "action": "review"}}])
completed_state = local_cleaner.state()
if completed_state.loc[completed_state["operator_name"] == "quality.blur_check", "status"].item() != "completed":
    raise AssertionError("quality.blur_check should be completed after rerun()")

local_result["parameter_table"] = pd.read_parquet(local_result["paths"].parameter_table_path)
local_result["evaluation_table"] = pd.read_parquet(local_result["paths"].evaluation_table_path)
local_result["preview"] = local_cleaner.preview()
completed_state
```

- [ ] **Step 2: Add export consistency cell**

Add a code cell:

```python
def export_and_validate_counts(result: dict[str, object]) -> dict[str, int]:
    label = str(result["label"])
    cleaner = result["cleaner"]
    export_dir = OUTPUT_DIR / label / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    datasets = {
        "full": cleaner.export("full", str(export_dir / "full.parquet")),
        "clean": cleaner.export("clean", str(export_dir / "clean.parquet")),
        "review": cleaner.export("review", str(export_dir / "review.parquet")),
        "dropped": cleaner.export("dropped", str(export_dir / "dropped.parquet")),
        "parameters": cleaner.export("parameters", str(export_dir / "parameters.parquet")),
        "evaluations": cleaner.export("evaluations", str(export_dir / "evaluations.parquet")),
    }
    counts = {name: dataset.count() for name, dataset in datasets.items()}
    restricted_count = result["preview"].restricted_count
    if counts["full"] != counts["clean"] + counts["review"] + counts["dropped"] + restricted_count:
        raise AssertionError(f"{label} export counts do not add up: {counts}, restricted={restricted_count}")
    if counts["parameters"] != counts["full"]:
        raise AssertionError(f"{label} parameters count should equal full count")
    if counts["evaluations"] != counts["full"]:
        raise AssertionError(f"{label} evaluations count should equal full count")
    return counts


local_counts = export_and_validate_counts(local_result)
minio_counts = export_and_validate_counts(minio_result)
local_counts, minio_counts
```

- [ ] **Step 3: Add final PASS cell**

Add a code cell:

```python
print("PASS: stage3 and stage4 operator validation completed")
```

- [ ] **Step 4: Verify notebook JSON contains final PASS marker**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("notebooks/operators_builtin_test.ipynb").read_text(encoding="utf-8"))
source = "\n".join("".join(cell.get("source", [])) for cell in data["cells"])
assert "PASS: stage3 and stage4 operator validation completed" in source
assert "Dataset.from_path(str(MINIO_RAW_DATASET_PATH), storage=minio_storage)" in source
assert "export_and_validate_counts" in source
print("notebook content ok")
PY
```

Expected: prints `notebook content ok`.

## Task 6: Run Validation Commands

**Files:**
- Verify: `notebooks/operators_builtin_test.ipynb`

- [ ] **Step 1: Run project tests**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run ruff**

Run:

```bash
.venv/bin/python -m ruff check src tests examples
```

Expected: `All checks passed!`

- [ ] **Step 3: Run mypy**

Run:

```bash
.venv/bin/python -m mypy src/image_gallery
```

Expected: `Success: no issues found`.

- [ ] **Step 4: Run notebook prerequisite script for MinIO**

Run the MinIO Dataset storage binding verification command from Task 3 Step 3.

Expected: prints `minio dataset image reading ok`.

If the command fails because `.env` is missing or MinIO is unavailable, do not modify notebook logic. Report the missing external prerequisite and leave the notebook ready for manual execution in a configured environment.

- [ ] **Step 5: Commit notebook**

Run:

```bash
git add notebooks/operators_builtin_test.ipynb
git commit -m "test: add operators validation notebook"
```

Expected: commit succeeds and only the notebook file is included in this commit.
