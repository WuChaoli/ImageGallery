# 清洗 v3 sample_1000 Notebook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `sample_1000/raw.parquet` 新增一套可复用的 Notebook helper 与分析型验证 Notebook，让后续 Notebook 直接复用 MinIO、Dataset、路径和第一批算子配置初始化逻辑。

**Architecture:** 保持现有 `src/image_gallery` 公共 API 不变，把 Notebook 专用装配逻辑收敛到 `notebooks/_helpers/`。Helper 只负责路径、环境变量、storage、Dataset 和算子配置初始化；`notebooks/cleaning_v3_sample_1000_test.ipynb` 负责组装、运行 `BasicCleaner`、读取 run 产物并展示统计与抽样。

**Tech Stack:** Python 3.10, Jupyter Notebook JSON, pandas, python-dotenv, pytest, existing `image_gallery` Dataset/MinioStorage/BasicCleaner APIs.

## Global Constraints

- 不修改 `ImportPipeline`、`Dataset`、`MinioStorage`、`BasicCleaner` 或 operator 的公共行为。
- 不重新生成默认 MinIO 数据集。
- 不把 Notebook 抽象成通用测试框架或一站式执行器。
- 不在第一版引入图片网格、HTML 报告或 Web UI。
- 不实现 `.env` 缺失时的降级模式；本 Notebook 强依赖 MinIO。
- 不自动执行 Notebook 作为 CI 测试；自动化覆盖以 helper 单测和现有集成测试为主。
- helper 负责初始化和轻量装配，Notebook 负责组装、运行和展示，不引入新的公共业务 API。

---

## File Structure

**Create**

- `notebooks/__init__.py`：让 `notebooks` 可以作为可导入包被 Notebook、测试和轻量脚本复用。
- `notebooks/_helpers/__init__.py`：导出 helper 子模块入口。
- `notebooks/_helpers/paths.py`：仓库根目录、Notebook 私有运行目录、输出目录重置。
- `notebooks/_helpers/storage.py`：`.env` 加载、MinIO 环境变量校验、`MinioStorage` 连接。
- `notebooks/_helpers/datasets.py`：sample_1000 raw dataset 路径定位、storage-backed `Dataset`、raw dataframe 读取。
- `notebooks/_helpers/cleaning_configs.py`：清洗 v3 第一批算子配置。
- `tests/unit/notebooks/test_paths_helper.py`
- `tests/unit/notebooks/test_storage_helper.py`
- `tests/unit/notebooks/test_datasets_helper.py`
- `tests/unit/notebooks/test_cleaning_configs_helper.py`
- `notebooks/cleaning_v3_sample_1000_test.ipynb`

**Modify**

- `tests/integration/cleaning/test_basic_cleaner_builtin_run.py`：复用 helper 中的 sample 路径、MinIO 初始化和第一批算子配置，消除重复定义。
- `notebooks/README.md`：补充新 Notebook 与 `_helpers/` 目录职责说明。
- `tests/unit/test_package_import.py`：增加 `notebooks` helper 包的可导入性检查。

## Task 1: Package Notebook Helpers For Import

**Files:**
- Create: `notebooks/__init__.py`
- Create: `notebooks/_helpers/__init__.py`
- Test: `tests/unit/test_package_import.py`

**Interfaces:**
- Consumes: existing repo root import path behavior from `pytest`
- Produces: `import notebooks`, `import notebooks._helpers`, `from notebooks._helpers import paths, storage, datasets, cleaning_configs`

- [ ] **Step 1: Write the failing package import test**

Append this test to `tests/unit/test_package_import.py`:

```python
def test_notebook_helper_modules_are_importable() -> None:
    module_names = [
        "notebooks",
        "notebooks._helpers",
        "notebooks._helpers.paths",
        "notebooks._helpers.storage",
        "notebooks._helpers.datasets",
        "notebooks._helpers.cleaning_configs",
    ]

    for module_name in module_names:
        assert importlib.import_module(module_name).__name__ == module_name
```

- [ ] **Step 2: Run the package import test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_package_import.py::test_notebook_helper_modules_are_importable -q
```

Expected: FAIL with `ModuleNotFoundError` because `notebooks` is not yet importable as a package.

- [ ] **Step 3: Create the package entry files**

Create `notebooks/__init__.py`:

```python
"""Notebook support package for reusable validation helpers."""
```

Create `notebooks/_helpers/__init__.py`:

```python
"""Reusable helpers for notebook validation flows."""

from notebooks._helpers import cleaning_configs, datasets, paths, storage

__all__ = [
    "cleaning_configs",
    "datasets",
    "paths",
    "storage",
]
```

- [ ] **Step 4: Run the package import test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_package_import.py::test_notebook_helper_modules_are_importable -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add notebooks/__init__.py notebooks/_helpers/__init__.py tests/unit/test_package_import.py
git commit -m "test: add notebook helper package imports"
```

## Task 2: Add Path And Storage Helpers

**Files:**
- Create: `notebooks/_helpers/paths.py`
- Create: `notebooks/_helpers/storage.py`
- Test: `tests/unit/notebooks/test_paths_helper.py`
- Test: `tests/unit/notebooks/test_storage_helper.py`

**Interfaces:**
- Consumes: `pathlib.Path`, `dotenv.load_dotenv`, `urllib.parse.urlparse`, `image_gallery.storage.MinioStorage`
- Produces:
  - `get_repo_root() -> Path`
  - `get_notebook_library_root(name: str) -> Path`
  - `reset_output_dir(path: Path) -> Path`
  - `read_required_env(name: str) -> str`
  - `load_minio_storage() -> MinioStorage`

- [ ] **Step 1: Write the failing path helper tests**

Create `tests/unit/notebooks/test_paths_helper.py`:

```python
from pathlib import Path

from notebooks._helpers.paths import get_notebook_library_root, get_repo_root, reset_output_dir


def test_get_repo_root_finds_pyproject() -> None:
    repo_root = get_repo_root()
    assert (repo_root / "pyproject.toml").exists()


def test_get_notebook_library_root_scopes_under_operators_test_library() -> None:
    library_root = get_notebook_library_root("cleaning_v3_sample_1000")
    assert library_root == get_repo_root() / "notebooks" / ".operators_test_library" / "cleaning_v3_sample_1000"


def test_reset_output_dir_recreates_empty_directory(tmp_path: Path) -> None:
    output_dir = tmp_path / "run"
    output_dir.mkdir(parents=True)
    nested = output_dir / "stale.txt"
    nested.write_text("stale", encoding="utf-8")

    reset_path = reset_output_dir(output_dir)

    assert reset_path == output_dir
    assert output_dir.exists()
    assert list(output_dir.iterdir()) == []
```

- [ ] **Step 2: Write the failing storage helper tests**

Create `tests/unit/notebooks/test_storage_helper.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from notebooks._helpers.storage import load_minio_storage, read_required_env


def test_read_required_env_returns_stripped_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_GALLERY_MINIO_ENDPOINT", "  http://127.0.0.1:9000  ")
    assert read_required_env("IMAGE_GALLERY_MINIO_ENDPOINT") == "http://127.0.0.1:9000"


def test_read_required_env_raises_for_missing_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IMAGE_GALLERY_MINIO_ENDPOINT", raising=False)

    with pytest.raises(RuntimeError, match="IMAGE_GALLERY_MINIO_ENDPOINT"):
        read_required_env("IMAGE_GALLERY_MINIO_ENDPOINT")


def test_load_minio_storage_uses_env_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAGE_GALLERY_MINIO_ENDPOINT", "https://minio.example.com")
    monkeypatch.setenv("IMAGE_GALLERY_MINIO_ACCESS_KEY", "access-key")
    monkeypatch.setenv("IMAGE_GALLERY_MINIO_SECRET_KEY", "secret-key")
    monkeypatch.setenv("IMAGE_GALLERY_MINIO_BUCKET", "bucket-a")

    storage = load_minio_storage()

    assert storage.bucket == "bucket-a"
    assert storage.endpoint == "minio.example.com"
    assert storage.secure is True
```

- [ ] **Step 3: Run the helper tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/notebooks/test_paths_helper.py tests/unit/notebooks/test_storage_helper.py -q
```

Expected: FAIL because the helper modules and functions do not exist yet.

- [ ] **Step 4: Implement the path helper**

Create `notebooks/_helpers/paths.py`:

```python
"""Path helpers for notebook validation flows."""

from __future__ import annotations

import shutil
from pathlib import Path


def get_repo_root() -> Path:
    """Locate the repository root by walking upward until pyproject.toml is found."""
    repo_root = Path.cwd().resolve()
    while repo_root != repo_root.parent and not (repo_root / "pyproject.toml").exists():
        repo_root = repo_root.parent
    if not (repo_root / "pyproject.toml").exists():
        raise RuntimeError("cannot locate repository root from current working directory")
    return repo_root


def get_notebook_library_root(name: str) -> Path:
    """Return the private runtime directory for a notebook validation flow."""
    return get_repo_root() / "notebooks" / ".operators_test_library" / name


def reset_output_dir(path: Path) -> Path:
    """Remove any previous runtime artifacts and recreate the directory."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path
```

- [ ] **Step 5: Implement the storage helper**

Create `notebooks/_helpers/storage.py`:

```python
"""MinIO initialization helpers for notebook validation flows."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from dotenv import load_dotenv

from image_gallery.storage import MinioStorage

from notebooks._helpers.paths import get_repo_root


def read_required_env(name: str) -> str:
    """Read one required environment variable and return a stripped value."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def load_minio_storage() -> MinioStorage:
    """Load MinIO settings from .env and return a connected storage instance."""
    load_dotenv(get_repo_root() / ".env")

    endpoint = read_required_env("IMAGE_GALLERY_MINIO_ENDPOINT")
    access_key = read_required_env("IMAGE_GALLERY_MINIO_ACCESS_KEY")
    secret_key = read_required_env("IMAGE_GALLERY_MINIO_SECRET_KEY")
    bucket = read_required_env("IMAGE_GALLERY_MINIO_BUCKET")

    parsed = urlparse(endpoint)
    connect_endpoint = parsed.netloc or endpoint
    secure = parsed.scheme == "https"

    return MinioStorage(storage_name="notebook_validation_minio").connect(
        endpoint=connect_endpoint,
        access_key=access_key,
        secret_key=secret_key,
        bucket=bucket,
        secure=secure,
    )
```

- [ ] **Step 6: Run the helper tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/unit/notebooks/test_paths_helper.py tests/unit/notebooks/test_storage_helper.py -q
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add notebooks/_helpers/paths.py notebooks/_helpers/storage.py tests/unit/notebooks/test_paths_helper.py tests/unit/notebooks/test_storage_helper.py
git commit -m "feat: add notebook path and storage helpers"
```

## Task 3: Add Dataset And Cleaning Config Helpers

**Files:**
- Create: `notebooks/_helpers/datasets.py`
- Create: `notebooks/_helpers/cleaning_configs.py`
- Test: `tests/unit/notebooks/test_datasets_helper.py`
- Test: `tests/unit/notebooks/test_cleaning_configs_helper.py`

**Interfaces:**
- Consumes: `pandas`, `image_gallery.dataset.Dataset`, `notebooks._helpers.paths.get_repo_root`, `notebooks._helpers.storage.load_minio_storage`
- Produces:
  - `get_default_minio_sample_1000_raw_path() -> Path`
  - `load_default_minio_sample_1000_dataset() -> Dataset`
  - `load_default_minio_sample_1000_frame() -> pd.DataFrame`
  - `get_cleaning_v3_first_batch_operator_configs() -> list[dict[str, dict[str, object]]]`

- [ ] **Step 1: Write the failing dataset helper tests**

Create `tests/unit/notebooks/test_datasets_helper.py`:

```python
from pathlib import Path

import pandas as pd
import pytest

from notebooks._helpers.datasets import (
    get_default_minio_sample_1000_raw_path,
    load_default_minio_sample_1000_dataset,
    load_default_minio_sample_1000_frame,
)


def test_get_default_minio_sample_1000_raw_path_points_to_expected_location() -> None:
    expected = Path("notebooks/.importers_test_library/default_minio_dataset/sample_1000/raw.parquet")
    assert get_default_minio_sample_1000_raw_path().as_posix().endswith(expected.as_posix())


def test_load_default_minio_sample_1000_frame_reads_existing_parquet() -> None:
    raw_path = get_default_minio_sample_1000_raw_path()
    if not raw_path.exists():
        pytest.skip(f"sample raw dataset not found: {raw_path}")

    frame = load_default_minio_sample_1000_frame()

    assert isinstance(frame, pd.DataFrame)
    assert "image_id" in frame.columns
    assert "image_uri" in frame.columns


def test_load_default_minio_sample_1000_dataset_requires_storage_backing() -> None:
    raw_path = get_default_minio_sample_1000_raw_path()
    if not raw_path.exists():
        pytest.skip(f"sample raw dataset not found: {raw_path}")

    dataset = load_default_minio_sample_1000_dataset()

    assert str(dataset.dataset_path).endswith("sample_1000/raw.parquet")
    assert dataset.storage is not None
```

- [ ] **Step 2: Write the failing cleaning config helper tests**

Create `tests/unit/notebooks/test_cleaning_configs_helper.py`:

```python
from notebooks._helpers.cleaning_configs import get_cleaning_v3_first_batch_operator_configs


def test_get_cleaning_v3_first_batch_operator_configs_returns_expected_order() -> None:
    operator_configs = get_cleaning_v3_first_batch_operator_configs()

    assert [next(iter(item.keys())) for item in operator_configs] == [
        "format.decode_check",
        "size.dimension_check",
        "size.aspect_ratio_check",
        "size.megapixel_check",
        "quality.blur_check",
        "quality.brightness_check",
        "quality.contrast_check",
        "content.blank_image_check",
        "duplicate.exact_duplicate_check",
    ]


def test_get_cleaning_v3_first_batch_operator_configs_uses_mapping_shape() -> None:
    for item in get_cleaning_v3_first_batch_operator_configs():
        assert isinstance(item, dict)
        assert len(item) == 1
        config = next(iter(item.values()))
        assert isinstance(config, dict)
```

- [ ] **Step 3: Run the helper tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/notebooks/test_datasets_helper.py tests/unit/notebooks/test_cleaning_configs_helper.py -q
```

Expected: FAIL because the dataset and config helpers do not exist yet.

- [ ] **Step 4: Implement the dataset helper**

Create `notebooks/_helpers/datasets.py`:

```python
"""Dataset helpers for notebook validation flows."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from image_gallery.dataset import Dataset

from notebooks._helpers.paths import get_repo_root
from notebooks._helpers.storage import load_minio_storage


def get_default_minio_sample_1000_raw_path() -> Path:
    """Return the raw parquet path for the default MinIO sample_1000 dataset."""
    return (
        get_repo_root()
        / "notebooks"
        / ".importers_test_library"
        / "default_minio_dataset"
        / "sample_1000"
        / "raw.parquet"
    )


def load_default_minio_sample_1000_dataset() -> Dataset:
    """Load the sample_1000 dataset with MinIO-backed image access."""
    raw_path = get_default_minio_sample_1000_raw_path()
    if not raw_path.exists():
        raise RuntimeError(f"sample raw dataset not found: {raw_path}")
    return Dataset.from_path(str(raw_path), storage=load_minio_storage())


def load_default_minio_sample_1000_frame() -> pd.DataFrame:
    """Load the sample_1000 raw parquet as a dataframe."""
    raw_path = get_default_minio_sample_1000_raw_path()
    if not raw_path.exists():
        raise RuntimeError(f"sample raw dataset not found: {raw_path}")
    return pd.read_parquet(raw_path)
```

- [ ] **Step 5: Implement the cleaning config helper**

Create `notebooks/_helpers/cleaning_configs.py`:

```python
"""Reusable operator configurations for notebook validation flows."""

from __future__ import annotations


def get_cleaning_v3_first_batch_operator_configs() -> list[dict[str, dict[str, object]]]:
    """Return the first-batch cleaning-v3 operators used by sample_1000 validation."""
    return [
        {"format.decode_check": {}},
        {"size.dimension_check": {"min_width": 10, "min_height": 10, "action": "review"}},
        {"size.aspect_ratio_check": {}},
        {"size.megapixel_check": {"min_megapixels": 0.00001}},
        {"quality.blur_check": {"min_score": 0.0}},
        {"quality.brightness_check": {}},
        {"quality.contrast_check": {"min_score": 0.0}},
        {"content.blank_image_check": {}},
        {"duplicate.exact_duplicate_check": {}},
    ]
```

- [ ] **Step 6: Run the helper tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/unit/notebooks/test_datasets_helper.py tests/unit/notebooks/test_cleaning_configs_helper.py -q
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add notebooks/_helpers/datasets.py notebooks/_helpers/cleaning_configs.py tests/unit/notebooks/test_datasets_helper.py tests/unit/notebooks/test_cleaning_configs_helper.py
git commit -m "feat: add notebook dataset and config helpers"
```

## Task 4: Refactor The Existing Integration Test To Reuse Helpers

**Files:**
- Modify: `tests/integration/cleaning/test_basic_cleaner_builtin_run.py`

**Interfaces:**
- Consumes:
  - `get_default_minio_sample_1000_raw_path() -> Path`
  - `load_minio_storage() -> MinioStorage`
  - `get_cleaning_v3_first_batch_operator_configs() -> list[dict[str, dict[str, object]]]`
- Produces: integration coverage that shares the same sample_1000 path and operator config source as the Notebook

- [ ] **Step 1: Write the failing refactor assertion**

Edit `tests/integration/cleaning/test_basic_cleaner_builtin_run.py` so the sample-path test includes:

```python
from notebooks._helpers.cleaning_configs import get_cleaning_v3_first_batch_operator_configs
from notebooks._helpers.datasets import get_default_minio_sample_1000_raw_path
from notebooks._helpers.storage import load_minio_storage
```

And replace the hard-coded assertions with:

```python
assert SAMPLE_DATASET_PATH == get_default_minio_sample_1000_raw_path()
assert list(state["operator_name"]) == [
    next(iter(item.keys()))
    for item in get_cleaning_v3_first_batch_operator_configs()
]
```

- [ ] **Step 2: Run the integration test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/integration/cleaning/test_basic_cleaner_builtin_run.py::test_basic_cleaner_runs_first_batch_operators_on_sample_1000_raw_parquet -q
```

Expected: FAIL because the helper imports or the refactored symbols are not wired yet.

- [ ] **Step 3: Complete the helper reuse refactor**

Update `tests/integration/cleaning/test_basic_cleaner_builtin_run.py` to this shape:

```python
from notebooks._helpers.cleaning_configs import get_cleaning_v3_first_batch_operator_configs
from notebooks._helpers.datasets import get_default_minio_sample_1000_raw_path
from notebooks._helpers.storage import load_minio_storage

SAMPLE_DATASET_PATH = get_default_minio_sample_1000_raw_path()
FIRST_BATCH_OPERATORS = get_cleaning_v3_first_batch_operator_configs()


def _build_sample_1000_dataset() -> Dataset:
    return Dataset.from_path(str(SAMPLE_DATASET_PATH), storage=load_minio_storage())
```

Delete the local `_read_env()` and `_connect_minio_storage()` helpers once the imports above replace them.

- [ ] **Step 4: Run the integration test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/integration/cleaning/test_basic_cleaner_builtin_run.py::test_basic_cleaner_runs_first_batch_operators_on_sample_1000_raw_parquet -q
```

Expected: PASS or SKIP with a message about missing sample dataset / storage connectivity; no import or helper wiring failures.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/cleaning/test_basic_cleaner_builtin_run.py
git commit -m "refactor: reuse notebook helpers in cleaning integration test"
```

## Task 5: Add The Sample_1000 Analysis Notebook

**Files:**
- Create: `notebooks/cleaning_v3_sample_1000_test.ipynb`
- Modify: `notebooks/README.md`

**Interfaces:**
- Consumes:
  - `get_notebook_library_root(name: str) -> Path`
  - `reset_output_dir(path: Path) -> Path`
  - `load_default_minio_sample_1000_frame() -> pd.DataFrame`
  - `load_default_minio_sample_1000_dataset() -> Dataset`
  - `get_cleaning_v3_first_batch_operator_configs() -> list[dict[str, dict[str, object]]]`
- Produces: human-readable analysis notebook for `sample_1000` with run artifacts, summary stats, and sampled rows

- [ ] **Step 1: Create the Notebook JSON with helper imports and setup cells**

Create `notebooks/cleaning_v3_sample_1000_test.ipynb` with early cells equivalent to:

```python
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from image_gallery.cleaning import BasicCleaner
from notebooks._helpers.cleaning_configs import get_cleaning_v3_first_batch_operator_configs
from notebooks._helpers.datasets import (
    get_default_minio_sample_1000_raw_path,
    load_default_minio_sample_1000_dataset,
    load_default_minio_sample_1000_frame,
)
from notebooks._helpers.paths import get_notebook_library_root, reset_output_dir

NOTEBOOK_NAME = "cleaning_v3_sample_1000"
RUN_ROOT = reset_output_dir(get_notebook_library_root(NOTEBOOK_NAME))
RUN_OUTPUT_DIR = RUN_ROOT / "outputs"
RUN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

raw_path = get_default_minio_sample_1000_raw_path()
raw_frame = load_default_minio_sample_1000_frame()
```

- [ ] **Step 2: Add the input validation and MinIO-backed dataset cells**

The Notebook must include cells equivalent to:

```python
assert "image_id" in raw_frame.columns
assert "image_uri" in raw_frame.columns
assert not raw_frame["image_uri"].isna().any()

print("raw_path:", raw_path)
print("raw_rows:", len(raw_frame))
print("raw_columns:", raw_frame.columns.tolist())
raw_frame.head()
```

```python
dataset = load_default_minio_sample_1000_dataset()

sample_uris = raw_frame["image_uri"].astype(str).head(3).tolist()
sample_images = []
for image_uri in sample_uris:
    image = dataset.read_image(image_uri)
    sample_images.append(
        {
            "image_uri": image_uri,
            "size": image.size,
            "format": image.format,
        }
    )

pd.DataFrame(sample_images)
```

- [ ] **Step 3: Add the BasicCleaner run and artifact inspection cells**

The Notebook must include cells equivalent to:

```python
operator_configs = get_cleaning_v3_first_batch_operator_configs()
cleaner = BasicCleaner(operator_configs)
cleaner.run(dataset, output_dir=RUN_OUTPUT_DIR)

preview = cleaner.preview()
state = cleaner.state()
context = cleaner._context
if context is None:
    raise AssertionError("cleaner context should exist")
paths = context.paths

parameter_table = pd.read_parquet(paths.parameter_table_path)
evaluation_table = pd.read_parquet(paths.evaluation_table_path)
parameter_manifest = json.loads(paths.parameter_manifest_path.read_text(encoding="utf-8"))
duplicate_pairs = pd.read_parquet(paths.relations_dir / "duplicate_pairs.parquet")

preview, state.head(), list(parameter_manifest.keys())[:10], duplicate_pairs.head()
```

And assert required columns:

```python
required_parameter_columns = {
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
required_evaluation_columns = {
    "decode_action",
    "decode_reason",
    "dimension_action",
    "dimension_reason",
    "aspect_ratio_action",
    "aspect_ratio_reason",
    "megapixel_action",
    "megapixel_reason",
    "blur_action",
    "blur_reason",
    "brightness_action",
    "brightness_reason",
    "contrast_action",
    "contrast_reason",
    "blank_action",
    "blank_reason",
    "exact_duplicate_action",
    "exact_duplicate_reason",
    "final_action",
    "final_reason",
    "triggered_operator_names",
}
assert required_parameter_columns.issubset(parameter_table.columns)
assert required_evaluation_columns.issubset(evaluation_table.columns)
```

- [ ] **Step 4: Add the summary statistics, sampling, and export cells**

The Notebook must include cells equivalent to:

```python
action_counts = evaluation_table["final_action"].value_counts(dropna=False).rename_axis("final_action").reset_index(name="count")

trigger_columns = [
    "decode_action",
    "dimension_action",
    "aspect_ratio_action",
    "megapixel_action",
    "blur_action",
    "brightness_action",
    "contrast_action",
    "blank_action",
    "exact_duplicate_action",
]
trigger_summary = pd.DataFrame(
    [
        {
            "column": column,
            "trigger_count": int((evaluation_table[column] != "keep").fillna(False).sum()),
        }
        for column in trigger_columns
    ]
)

duplicate_summary = pd.DataFrame(
    [
        {
            "duplicate_rows": int((parameter_table["exact_duplicate_count"] > 1).fillna(False).sum()),
            "duplicate_groups": int(parameter_table["exact_duplicate_group_id"].dropna().nunique()),
            "max_group_size": int(parameter_table["exact_duplicate_count"].fillna(0).max()),
        }
    ]
)

action_counts, trigger_summary, duplicate_summary
```

```python
analysis_frame = parameter_table.merge(
    evaluation_table[
        [
            "image_id",
            "final_action",
            "final_reason",
            "blank_action",
            "blank_reason",
            "dimension_action",
            "dimension_reason",
            "exact_duplicate_action",
            "exact_duplicate_reason",
        ]
    ],
    on="image_id",
    how="left",
)

def sample_rows(frame: pd.DataFrame, query: str, limit: int = 5) -> pd.DataFrame:
    sampled = frame.query(query, engine="python").head(limit)
    columns = [
        "image_id",
        "image_uri",
        "blur_score",
        "brightness_score",
        "contrast_score",
        "blank_score",
        "exact_duplicate_count",
        "final_action",
        "final_reason",
        "blank_reason",
        "dimension_reason",
        "exact_duplicate_reason",
    ]
    existing_columns = [column for column in columns if column in sampled.columns]
    return sampled[existing_columns]

sample_rows(analysis_frame, "final_action == 'keep'")
sample_rows(analysis_frame, "final_action == 'review'")
sample_rows(analysis_frame, "final_action == 'drop'")
sample_rows(analysis_frame, "blank_action != 'keep'")
sample_rows(analysis_frame, "dimension_action != 'keep'")
sample_rows(analysis_frame, "exact_duplicate_action != 'keep'")
```

```python
full_export = cleaner.export("full", str(RUN_ROOT / "full.parquet")).to_frame()
dropped_export = cleaner.export("dropped", str(RUN_ROOT / "dropped.parquet")).to_frame()

assert len(full_export) == len(evaluation_table)
assert len(dropped_export) == int((evaluation_table["final_action"] == "drop").sum())

full_export.head(), dropped_export.head()
```

- [ ] **Step 5: Update the Notebook README entry**

Edit `notebooks/README.md` to this shape:

```markdown
# Notebooks

This directory will contain Jupyter validation flows for each development stage.

Stage 0 only keeps the directory entrypoint. Business validation notebooks start after Stage 1.

- `_helpers/`: Notebook 与轻量测试脚本共享的初始化 helper，包括路径、MinIO storage、sample_1000 dataset 和清洗 v3 第一批算子配置。
- `cleaning_v3_sample_1000_test.ipynb`: 基于 default MinIO sample_1000 raw dataset 的清洗 v3 第一批算子分析型验证入口。
- `cleaning_v3_builtin_test.ipynb`: 自包含验证 V3 清洗平台第一批内置算子，包括质量、空白图和完全重复检查，不依赖 MinIO 或 importer 产物。
- `operators_builtin_test.ipynb`: 基于 importer 产物和可选 MinIO 环境验证内置算子流程。
```

- [ ] **Step 6: Validate the Notebook JSON and README update**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

notebook_path = Path("notebooks/cleaning_v3_sample_1000_test.ipynb")
payload = json.loads(notebook_path.read_text(encoding="utf-8"))
assert payload["nbformat"] == 4
sources = ["".join(cell.get("source", [])) for cell in payload["cells"] if cell.get("cell_type") == "code"]
assert any("load_default_minio_sample_1000_dataset" in source for source in sources)
assert any("get_cleaning_v3_first_batch_operator_configs" in source for source in sources)
assert "cleaning_v3_sample_1000_test.ipynb" in Path("notebooks/README.md").read_text(encoding="utf-8")
print("notebook json ok")
PY
```

Expected: `notebook json ok`

- [ ] **Step 7: Commit**

```bash
git add notebooks/cleaning_v3_sample_1000_test.ipynb notebooks/README.md
git commit -m "feat: add cleaning v3 sample 1000 notebook"
```

## Task 6: Verify Helper Tests And Integration Coverage

**Files:**
- Test: `tests/unit/test_package_import.py`
- Test: `tests/unit/notebooks/test_paths_helper.py`
- Test: `tests/unit/notebooks/test_storage_helper.py`
- Test: `tests/unit/notebooks/test_datasets_helper.py`
- Test: `tests/unit/notebooks/test_cleaning_configs_helper.py`
- Test: `tests/integration/cleaning/test_basic_cleaner_builtin_run.py`

**Interfaces:**
- Consumes: all helper functions and the existing cleaning integration test
- Produces: automated verification that helper behavior and integration wiring are stable

- [ ] **Step 1: Run the focused helper and integration tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/unit/test_package_import.py \
  tests/unit/notebooks/test_paths_helper.py \
  tests/unit/notebooks/test_storage_helper.py \
  tests/unit/notebooks/test_datasets_helper.py \
  tests/unit/notebooks/test_cleaning_configs_helper.py \
  tests/integration/cleaning/test_basic_cleaner_builtin_run.py -q
```

Expected: PASS, except the sample_1000 integration case may SKIP if the dataset or MinIO connectivity is unavailable.

- [ ] **Step 2: Run the broader static checks**

Run:

```bash
.venv/bin/python -m ruff check notebooks tests
.venv/bin/python -m mypy src/image_gallery
```

Expected: PASS

- [ ] **Step 3: Commit the verification-complete state**

```bash
git add tests/unit/notebooks tests/unit/test_package_import.py tests/integration/cleaning/test_basic_cleaner_builtin_run.py notebooks/README.md notebooks/_helpers notebooks/cleaning_v3_sample_1000_test.ipynb
git commit -m "test: verify notebook helper validation flow"
```
