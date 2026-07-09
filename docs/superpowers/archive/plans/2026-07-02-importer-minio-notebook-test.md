# Importer MinIO Notebook Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone notebook that validates importing local directory images into MinIO through the existing `ImportPipeline`.

**Architecture:** The notebook reuses `LocalDirectoryReader`, `ImportPipeline`, `Dataset`, and `MinioStorage`; no importer or storage production code changes are needed. MinIO credentials are loaded from the repository root `.env`, outputs are isolated under `notebooks/.importers_test_library/minio_outputs/`, and validation cells assert both raw dataset format and sampled object readability.

**Tech Stack:** Python 3.10, Jupyter notebook JSON, `python-dotenv`, pandas, MinIO SDK through `image_gallery.storage.MinioStorage`, existing `image_gallery` package APIs.

---

## File Structure

- Create: `notebooks/importers_minio_test.ipynb`
  - Standalone manual validation notebook for local-directory-to-MinIO importer flow.
  - Contains environment loading, storage connection, import execution, raw dataset checks, sampled MinIO readback, and preview cells.
- No production code changes.
- No automated test file changes.

## Task 1: Create MinIO Importer Notebook

**Files:**
- Create: `notebooks/importers_minio_test.ipynb`

- [ ] **Step 1: Generate the notebook JSON**

Run this command from the repository root:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

notebook = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# Importers MinIO Test\n",
                "\n",
                "导入 Windows 图片目录 `C:\\\\Users\\\\wuchaoli\\\\Pictures\\\\测试图片`，并写入 MinIO 受管图片库。Notebook 运行产物统一写入 `notebooks/.importers_test_library/minio_outputs/`。MinIO 连接参数从仓库根目录 `.env` 读取。\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import os\n",
                "from pathlib import Path\n",
                "from urllib.parse import urlparse\n",
                "\n",
                "from dotenv import load_dotenv\n",
                "\n",
                "from image_gallery.importers import ImportPipeline, LocalDirectoryReader\n",
                "from image_gallery.storage import MinioStorage\n",
                "\n",
                "\n",
                "repo_root = Path.cwd()\n",
                "if not (repo_root / \"pyproject.toml\").exists():\n",
                "    repo_root = repo_root.parent\n",
                "load_dotenv(repo_root / \".env\")\n",
                "\n",
                "\n",
                "def require_env(name: str) -> str:\n",
                "    value = os.getenv(name)\n",
                "    if not value:\n",
                "        raise RuntimeError(f\"Missing required environment variable: {name}\")\n",
                "    return value\n",
                "\n",
                "\n",
                "raw_endpoint = require_env(\"IMAGE_GALLERY_MINIO_ENDPOINT\")\n",
                "access_key = require_env(\"IMAGE_GALLERY_MINIO_ACCESS_KEY\")\n",
                "secret_key = require_env(\"IMAGE_GALLERY_MINIO_SECRET_KEY\")\n",
                "bucket = require_env(\"IMAGE_GALLERY_MINIO_BUCKET\")\n",
                "\n",
                "parsed = urlparse(raw_endpoint)\n",
                "endpoint = parsed.netloc or raw_endpoint\n",
                "secure = parsed.scheme == \"https\"\n",
                "\n",
                "windows_source_dir = Path(r\"C:\\Users\\wuchaoli\\Pictures\\测试图片\")\n",
                "wsl_source_dir = Path(\"/mnt/c/Users/wuchaoli/Pictures/测试图片\")\n",
                "source_dir = wsl_source_dir if wsl_source_dir.exists() else windows_source_dir\n",
                "if not source_dir.exists():\n",
                "    raise FileNotFoundError(f\"source directory not found: {source_dir}\")\n",
                "\n",
                "library_root = repo_root / \"notebooks\" / \".importers_test_library\"\n",
                "output_dir = library_root / \"minio_outputs\"\n",
                "records = LocalDirectoryReader(source_dir).read()\n",
                "\n",
                "print(\"source_dir:\", source_dir)\n",
                "print(\"output_dir:\", output_dir)\n",
                "print(\"bucket:\", bucket)\n",
                "print(\"secure:\", secure)\n",
                "print(\"source records:\", len(records))\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "storage = MinioStorage(storage_name=\"minio_test_picture_library\").connect(\n",
                "    endpoint=endpoint,\n",
                "    access_key=access_key,\n",
                "    secret_key=secret_key,\n",
                "    bucket=bucket,\n",
                "    secure=secure,\n",
                ")\n",
                "\n",
                "print(\"connected bucket:\", storage.bucket)\n",
                "print(\"storage_name:\", storage.storage_name)\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "result = ImportPipeline(\n",
                "    storage=storage,\n",
                "    output_dir=output_dir,\n",
                "    global_tags=[\"dataset/test_pictures\", \"source/windows_pictures\", \"storage/minio\"],\n",
                ").run(records)\n",
                "\n",
                "print(\"raw_dataset_path:\", result.raw_dataset_path)\n",
                "print(\"import_report_path:\", result.import_report_path)\n",
                "print(\"failure_manifest_path:\", result.failure_manifest_path)\n",
                "print(\"report:\", result.report)\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import uuid\n",
                "from datetime import datetime\n",
                "from pathlib import PurePosixPath\n",
                "\n",
                "from image_gallery.dataset import Dataset\n",
                "\n",
                "\n",
                "raw_frame = Dataset.from_path(result.raw_dataset_path).to_frame()\n",
                "today = datetime.now().date().isoformat()\n",
                "image_uri_prefix = f\"s3://{bucket}/images/raw/\"\n",
                "\n",
                "if raw_frame.empty:\n",
                "    raise AssertionError(\"raw dataset should contain imported rows\")\n",
                "if not raw_frame[\"image_uri\"].str.startswith(image_uri_prefix).all():\n",
                "    raise AssertionError(f\"image_uri should start with {image_uri_prefix}\")\n",
                "if not raw_frame[\"image_uri\"].str.contains(f\"images/raw/{today}/shard_\").all():\n",
                "    raise AssertionError(\"image_uri should contain today's date shard path\")\n",
                "if not (raw_frame[\"storage_name\"] == \"minio_test_picture_library\").all():\n",
                "    raise AssertionError(\"storage_name should be minio_test_picture_library\")\n",
                "\n",
                "for row in raw_frame.itertuples(index=False):\n",
                "    object_name = str(row.image_uri).removeprefix(f\"s3://{bucket}/\")\n",
                "    managed_name = PurePosixPath(object_name).name\n",
                "    uuid.UUID(PurePosixPath(managed_name).stem)\n",
                "    if managed_name == row.source_file_name:\n",
                "        raise AssertionError(\"managed MinIO object should not expose source_file_name\")\n",
                "    if not managed_name.endswith(PurePosixPath(row.source_file_name).suffix.lower()):\n",
                "        raise AssertionError(\"managed MinIO object should preserve lowercase source extension\")\n",
                "\n",
                "print(\"raw rows:\", len(raw_frame))\n",
                "print(raw_frame.head())\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "sample_rows = raw_frame.head(5)\n",
                "readback = []\n",
                "for row in sample_rows.itertuples(index=False):\n",
                "    object_path = str(row.image_uri).removeprefix(f\"s3://{bucket}/\")\n",
                "    data = storage.read_bytes(object_path)\n",
                "    if not data:\n",
                "        raise AssertionError(f\"empty object data: {object_path}\")\n",
                "    readback.append({\"object_path\": object_path, \"bytes\": len(data)})\n",
                "\n",
                "readback\n",
            ],
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "preview_columns = [\n",
                "    \"source_file_name\",\n",
                "    \"image_uri\",\n",
                "    \"image_format\",\n",
                "    \"width\",\n",
                "    \"height\",\n",
                "    \"file_size_bytes\",\n",
                "]\n",
                "raw_frame[preview_columns].head(20)\n",
            ],
        },
    ],
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

Path("notebooks/importers_minio_test.ipynb").write_text(
    json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
    encoding="utf-8",
)
PY
```

Expected: `notebooks/importers_minio_test.ipynb` exists and contains 7 cells.

- [ ] **Step 2: Validate notebook JSON shape**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path

path = Path("notebooks/importers_minio_test.ipynb")
data = json.loads(path.read_text(encoding="utf-8"))
assert data["nbformat"] == 4
assert len(data["cells"]) == 7
assert data["cells"][0]["cell_type"] == "markdown"
assert all("execution_count" in cell for cell in data["cells"] if cell["cell_type"] == "code")
print(path, "cells:", len(data["cells"]))
PY
```

Expected: prints `notebooks/importers_minio_test.ipynb cells: 7`.

- [ ] **Step 3: Run a non-secret notebook content check**

Run:

```bash
.venv/bin/python - <<'PY'
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(".env")
content = Path("notebooks/importers_minio_test.ipynb").read_text(encoding="utf-8")
for name in [
    "IMAGE_GALLERY_MINIO_ENDPOINT",
    "IMAGE_GALLERY_MINIO_ACCESS_KEY",
    "IMAGE_GALLERY_MINIO_SECRET_KEY",
]:
    value = os.getenv(name)
    if value and value in content:
        raise AssertionError(f"notebook contains concrete secret/config value from {name}")
print("notebook contains env variable names only")
PY
```

Expected: prints `notebook contains env variable names only`.

- [ ] **Step 4: Commit notebook creation**

Run:

```bash
git add notebooks/importers_minio_test.ipynb
git commit -m "test: add minio importer notebook"
```

Expected: commit succeeds with one new notebook file.

## Task 2: Execute MinIO Importer Validation

**Files:**
- Verify: `notebooks/importers_minio_test.ipynb`
- Generated ignored outputs: `notebooks/.importers_test_library/minio_outputs/raw.parquet`
- Generated ignored outputs: `notebooks/.importers_test_library/minio_outputs/import_report.json`
- Generated ignored outputs: `notebooks/.importers_test_library/minio_outputs/failure_manifest.jsonl`

- [ ] **Step 1: Run notebook through nbconvert if available**

Run:

```bash
.venv/bin/python -m jupyter nbconvert --to notebook --execute notebooks/importers_minio_test.ipynb --output importers_minio_test.executed.ipynb --output-dir /tmp
```

Expected: command exits 0 and `/tmp/importers_minio_test.executed.ipynb` is created.

If `jupyter` is not installed in `.venv`, run Step 2 instead.

- [ ] **Step 2: Run equivalent validation script if nbconvert is unavailable**

Run:

```bash
.venv/bin/python - <<'PY'
import os
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from dotenv import load_dotenv

from image_gallery.dataset import Dataset
from image_gallery.importers import ImportPipeline, LocalDirectoryReader
from image_gallery.storage import MinioStorage

repo_root = Path.cwd()
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

wsl_source_dir = Path("/mnt/c/Users/wuchaoli/Pictures/测试图片")
windows_source_dir = Path(r"C:\Users\wuchaoli\Pictures\测试图片")
source_dir = wsl_source_dir if wsl_source_dir.exists() else windows_source_dir
if not source_dir.exists():
    raise FileNotFoundError(f"source directory not found: {source_dir}")

storage = MinioStorage(storage_name="minio_test_picture_library").connect(
    endpoint=endpoint,
    access_key=access_key,
    secret_key=secret_key,
    bucket=bucket,
    secure=secure,
)
records = LocalDirectoryReader(source_dir).read()
result = ImportPipeline(
    storage=storage,
    output_dir=repo_root / "notebooks" / ".importers_test_library" / "minio_outputs",
    global_tags=["dataset/test_pictures", "source/windows_pictures", "storage/minio"],
).run(records)

raw_frame = Dataset.from_path(result.raw_dataset_path).to_frame()
today = datetime.now().date().isoformat()
prefix = f"s3://{bucket}/images/raw/"
assert not raw_frame.empty
assert raw_frame["image_uri"].str.startswith(prefix).all()
assert raw_frame["image_uri"].str.contains(f"images/raw/{today}/shard_").all()
assert (raw_frame["storage_name"] == "minio_test_picture_library").all()

for row in raw_frame.head(5).itertuples(index=False):
    object_path = str(row.image_uri).removeprefix(f"s3://{bucket}/")
    name = PurePosixPath(object_path).name
    uuid.UUID(PurePosixPath(name).stem)
    assert name != row.source_file_name
    assert name.endswith(PurePosixPath(row.source_file_name).suffix.lower())
    assert storage.read_bytes(object_path)

print("success_count:", result.report["success_count"])
print("failure_count:", result.report["failure_count"])
print("raw_dataset_path:", result.raw_dataset_path)
PY
```

Expected: prints success count, failure count, and raw dataset path without raising an exception.

- [ ] **Step 3: Confirm expected ignored outputs exist**

Run:

```bash
ls -l notebooks/.importers_test_library/minio_outputs
```

Expected: output includes `raw.parquet`, `import_report.json`, and `failure_manifest.jsonl`.

- [ ] **Step 4: Confirm git only tracks intended source changes**

Run:

```bash
git status --short
```

Expected: clean worktree after Task 1 commit, because `.gitignore` excludes `.env` and `notebooks/.importers_test_library/`.
