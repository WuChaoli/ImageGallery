# Default MinIO Dataset Build Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Notebook-driven process that imports the vehicle image source directory into MinIO and writes full plus deterministic 1000-row sample raw datasets.

**Architecture:** Create one dedicated Notebook under `notebooks/` that uses existing `ImportPipeline`, `MinioStorage`, and `Dataset` APIs. The Notebook performs the full MinIO import once, derives the 1000-row sample from the full raw dataset without re-uploading images, and verifies a small set of referenced MinIO objects can be read.

**Tech Stack:** Python 3.10, Jupyter Notebook JSON, pandas, python-dotenv, MinIO SDK through existing `MinioStorage`, existing ImageGallery package APIs.

---

## File Structure

- Create: `notebooks/default_minio_dataset_build.ipynb`
  - Responsibility: executable Notebook for full import, sample derivation, and validation.
- Runtime output: `notebooks/.importers_test_library/default_minio_dataset/full/`
  - Responsibility: full importer outputs, including `raw.parquet`.
- Runtime output: `notebooks/.importers_test_library/default_minio_dataset/sample_1000/`
  - Responsibility: deterministic sample outputs, including `raw.parquet` and `import_report.json`.
- No source package files change.

### Task 1: Create Default MinIO Dataset Build Notebook

**Files:**
- Create: `notebooks/default_minio_dataset_build.ipynb`

- [ ] **Step 1: Create the Notebook with setup, import, sampling, and validation cells**

Create `notebooks/default_minio_dataset_build.ipynb` with cells equivalent to this Python flow:

```python
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from dotenv import load_dotenv

from image_gallery.dataset import Dataset
from image_gallery.importers import ImportPipeline
from image_gallery.importers.local_path import SUPPORTED_IMAGE_SUFFIXES
from image_gallery.storage import MinioStorage

repo_root = Path.cwd()
while repo_root != repo_root.parent and not (repo_root / "pyproject.toml").exists():
    repo_root = repo_root.parent
if not (repo_root / "pyproject.toml").exists():
    raise RuntimeError("cannot locate repository root from current working directory")

load_dotenv(repo_root / ".env")

source_dir = Path("/mnt/c/Users/wuchaoli/Pictures/5月22日小车采集图（原始数据）")
if not source_dir.exists():
    raise RuntimeError(f"source directory does not exist: {source_dir}")

library_root = repo_root / "notebooks" / ".importers_test_library" / "default_minio_dataset"
full_dir = library_root / "full"
sample_dir = library_root / "sample_1000"
sample_size = 1000
random_state = 20260706

image_paths = sorted(
    path
    for path in source_dir.rglob("*")
    if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
)
if len(image_paths) < sample_size:
    raise RuntimeError(f"source image count {len(image_paths)} is less than sample size {sample_size}")
```

- [ ] **Step 2: Ensure the Notebook connects to MinIO through `.env`**

The Notebook must include this helper logic:

```python
def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def parse_minio_endpoint(raw_endpoint: str) -> tuple[str, bool]:
    parsed = urlparse(raw_endpoint)
    if parsed.scheme in {"http", "https"}:
        return parsed.netloc, parsed.scheme == "https"
    return raw_endpoint, False


raw_endpoint = require_env("IMAGE_GALLERY_MINIO_ENDPOINT")
access_key = require_env("IMAGE_GALLERY_MINIO_ACCESS_KEY")
secret_key = require_env("IMAGE_GALLERY_MINIO_SECRET_KEY")
bucket = require_env("IMAGE_GALLERY_MINIO_BUCKET")
endpoint, secure = parse_minio_endpoint(raw_endpoint)

storage = MinioStorage(storage_name="default_minio_test_dataset").connect(
    endpoint=endpoint,
    access_key=access_key,
    secret_key=secret_key,
    bucket=bucket,
    secure=secure,
)
```

- [ ] **Step 3: Ensure the Notebook performs full import**

The Notebook must run:

```python
result = ImportPipeline(
    source=source_dir,
    storage=storage,
    output_dir=full_dir,
    global_tags=[
        "dataset/default_minio",
        "dataset/full",
        "source/windows_pictures",
        "source/vehicle_20240522",
        "storage/minio",
    ],
).run()

print("source_dir:", source_dir)
print("source_image_count:", len(image_paths))
print("bucket:", bucket)
print("full_raw_dataset_path:", result.raw_dataset_path)
print("full_import_report:", result.report)
```

- [ ] **Step 4: Ensure the Notebook derives and writes the sample dataset**

The Notebook must run:

```python
full_dataset = Dataset.from_path(result.raw_dataset_path)
full_frame = full_dataset.to_frame()
if len(full_frame) < sample_size:
    raise RuntimeError(f"full success count {len(full_frame)} is less than sample size {sample_size}")

sample_frame = full_frame.sample(n=sample_size, random_state=random_state).sort_values("image_id").reset_index(drop=True)
if sample_frame["image_uri"].isna().any():
    raise RuntimeError("sample contains empty image_uri values")
if not set(sample_frame["image_id"]).issubset(set(full_frame["image_id"])):
    raise RuntimeError("sample contains image_id values not present in full dataset")

sample_dir.mkdir(parents=True, exist_ok=True)
sample_dataset_path = sample_dir / "raw.parquet"
Dataset.write(sample_frame, str(sample_dataset_path))

sample_report = {
    "source_raw_dataset_path": str(Path(result.raw_dataset_path).resolve()),
    "source_row_count": int(len(full_frame)),
    "sample_size": sample_size,
    "random_state": random_state,
}
(sample_dir / "import_report.json").write_text(
    json.dumps(sample_report, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("sample_raw_dataset_path:", sample_dataset_path)
print("sample_report:", sample_report)
```

- [ ] **Step 5: Ensure the Notebook validates MinIO object reads**

The Notebook must include:

```python
def object_path_from_s3_uri(image_uri: str, expected_bucket: str) -> str:
    parsed = urlparse(image_uri)
    if parsed.scheme != "s3":
        raise RuntimeError(f"image_uri is not s3: {image_uri}")
    if parsed.netloc != expected_bucket:
        raise RuntimeError(f"image_uri bucket {parsed.netloc} does not match expected bucket {expected_bucket}")
    object_path = parsed.path.lstrip("/")
    if not object_path:
        raise RuntimeError(f"image_uri has empty object path: {image_uri}")
    return object_path


for label, frame in [("full", full_frame), ("sample_1000", sample_frame)]:
    prefix = f"s3://{bucket}/images/raw/"
    if not frame["image_uri"].astype(str).str.startswith(prefix).all():
        raise RuntimeError(f"{label} dataset contains image_uri outside expected prefix {prefix}")

read_check_rows = sample_frame.head(10)
for image_uri in read_check_rows["image_uri"].astype(str):
    data = storage.read_bytes(object_path_from_s3_uri(image_uri, bucket))
    if not data:
        raise RuntimeError(f"empty object bytes: {image_uri}")

print("read_check_count:", len(read_check_rows))
print("validation_status: ok")
```

- [ ] **Step 6: Validate Notebook JSON exists**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("notebooks/default_minio_dataset_build.ipynb")
data = json.loads(path.read_text(encoding="utf-8"))
assert data["nbformat"] == 4
assert any("ImportPipeline" in "".join(cell.get("source", [])) for cell in data["cells"])
assert any("sample_size = 1000" in "".join(cell.get("source", [])) for cell in data["cells"])
print("notebook json ok")
PY
```

Expected: `notebook json ok`

### Task 2: Execute Notebook Flow and Verify Generated Datasets

**Files:**
- Runtime output: `notebooks/.importers_test_library/default_minio_dataset/full/raw.parquet`
- Runtime output: `notebooks/.importers_test_library/default_minio_dataset/sample_1000/raw.parquet`

- [ ] **Step 1: Run the Notebook flow as a Python smoke execution**

Run the Notebook cells in order through `nbconvert` if available:

```bash
.venv/bin/python -m jupyter nbconvert --to notebook --execute notebooks/default_minio_dataset_build.ipynb --output default_minio_dataset_build.executed.ipynb --output-dir notebooks
```

Expected: command exits `0`.

If `jupyter` is not installed, run the same cell logic with `.venv/bin/python` directly and keep `notebooks/default_minio_dataset_build.ipynb` as the user-facing artifact.

- [ ] **Step 2: Verify full and sample raw datasets**

Run:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import pandas as pd

full_path = Path("notebooks/.importers_test_library/default_minio_dataset/full/raw.parquet")
sample_path = Path("notebooks/.importers_test_library/default_minio_dataset/sample_1000/raw.parquet")
assert full_path.exists(), full_path
assert sample_path.exists(), sample_path
full = pd.read_parquet(full_path)
sample = pd.read_parquet(sample_path)
assert len(full) >= 1000, len(full)
assert len(sample) == 1000, len(sample)
assert set(sample["image_id"]).issubset(set(full["image_id"]))
assert sample["image_uri"].astype(str).str.startswith("s3://").all()
print({"full_rows": len(full), "sample_rows": len(sample)})
PY
```

Expected: printed row counts with `sample_rows` equal to `1000`.

- [ ] **Step 3: Run focused quality checks**

Run:

```bash
.venv/bin/python -m ruff check notebooks/default_minio_dataset_build.ipynb
```

Expected: `All checks passed!`

If ruff cannot parse Notebook input in the installed version, skip this command and rely on Notebook JSON validation plus execution verification.

- [ ] **Step 4: Commit implementation artifact**

Run:

```bash
git add notebooks/default_minio_dataset_build.ipynb
git commit -m "chore: add default minio dataset notebook"
```

Expected: commit includes only `notebooks/default_minio_dataset_build.ipynb`.
