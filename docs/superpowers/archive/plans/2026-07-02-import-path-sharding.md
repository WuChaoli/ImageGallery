# Import Path Sharding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change imported image storage paths from `images/raw/<uuid>/<original-name>` to date/shard/UUID filenames such as `images/raw/2026-07-02/shard_001/<uuid>.jpg`.

**Architecture:** Keep the change inside `ImportPipeline`, because path generation is part of the storage write orchestration. Preserve `source_file_name` in raw Dataset for traceability and do not add schema fields. Add a small private helper for path construction and expose only `max_shard_size` as a constructor parameter with default `10000`.

**Tech Stack:** Python 3.10, pathlib, uuid, pytest, pandas, Pillow.

---

## File Structure

Modify:

- `src/image_gallery/importers/pipeline.py`: add `max_shard_size`, validate it, compute date/shard object paths, and add `_build_raw_object_path()`.
- `tests/unit/importers/test_import_pipeline.py`: assert UUID filename behavior, date/shard path layout, lowercase extension preservation, and shard rollover.
- `notebooks/importers_local_directory_test.ipynb`: no source change required, but rerun its import flow to validate new storage layout.

## Task 1: Pipeline Path Tests

- [ ] **Step 1: Update `tests/unit/importers/test_import_pipeline.py` imports**

Add:

```python
import uuid
from datetime import datetime
```

- [ ] **Step 2: Strengthen the existing pipeline test**

After loading `raw_frame`, add assertions:

```python
managed_path = Path(raw_frame.iloc[0]["image_uri"])
today = datetime.now().date().isoformat()

assert managed_path.name != "a.jpg"
assert managed_path.suffix == ".jpg"
uuid.UUID(managed_path.stem)
assert f"images/raw/{today}/shard_001" in managed_path.as_posix()
assert raw_frame.iloc[0]["source_file_name"] == "a.jpg"
```

- [ ] **Step 3: Add shard rollover test**

Create a second test:

```python
def test_import_pipeline_rolls_over_shards_by_success_count(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    Image.new("RGB", (4, 2), color="blue").save(source_dir / "a.JPG")
    (source_dir / "bad.jpg").write_bytes(b"not an image")
    Image.new("RGB", (4, 2), color="green").save(source_dir / "b.png")

    storage = FileSystemStorage(storage_name="local_main").connect(root=tmp_path / "storage")
    pipeline = ImportPipeline(storage=storage, output_dir=tmp_path / "outputs", max_shard_size=1)

    result = pipeline.run(LocalDirectoryReader(source_dir).read())

    raw_frame = Dataset.from_path(result.raw_dataset_path).to_frame().sort_values("source_file_name")
    image_paths = [Path(image_uri) for image_uri in raw_frame["image_uri"]]
    today = datetime.now().date().isoformat()

    assert f"images/raw/{today}/shard_001" in image_paths[0].as_posix()
    assert image_paths[0].suffix == ".jpg"
    uuid.UUID(image_paths[0].stem)
    assert f"images/raw/{today}/shard_002" in image_paths[1].as_posix()
    assert image_paths[1].suffix == ".png"
    uuid.UUID(image_paths[1].stem)
    assert result.report == {"success_count": 2, "failure_count": 1}
```

- [ ] **Step 4: Add constructor validation test**

```python
def test_import_pipeline_rejects_invalid_max_shard_size(tmp_path: Path) -> None:
    storage = FileSystemStorage(storage_name="local_main").connect(root=tmp_path / "storage")

    with pytest.raises(ValueError, match="max_shard_size must be greater than 0"):
        ImportPipeline(storage=storage, output_dir=tmp_path / "outputs", max_shard_size=0)
```

- [ ] **Step 5: Run tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/unit/importers/test_import_pipeline.py -q
```

Expected: FAIL because the implementation still uses `images/raw/<uuid>/<source_file_name>` and does not accept `max_shard_size`.

## Task 2: Pipeline Implementation

- [ ] **Step 1: Update `ImportPipeline.__init__()` signature**

Change:

```python
global_tags: Iterable[str] | None = None,
```

To:

```python
global_tags: Iterable[str] | None = None,
max_shard_size: int = 10000,
```

- [ ] **Step 2: Validate and store shard size**

Add after `self.global_tags`:

```python
if max_shard_size <= 0:
    raise ValueError("max_shard_size must be greater than 0")
self.max_shard_size = max_shard_size
```

- [ ] **Step 3: Compute local import date once per run**

At the start of `run()` after `self.output_dir.mkdir(...)`, add:

```python
import_date = datetime.now().date().isoformat()
```

- [ ] **Step 4: Replace object path generation**

Replace:

```python
object_path = f"images/raw/{image_id}/{record.source_file_name}"
```

With:

```python
shard_index = len(imported_rows) // self.max_shard_size + 1
object_path = _build_raw_object_path(import_date, shard_index, image_id, record.source_file_name)
```

- [ ] **Step 5: Add helper**

Add below `_unique_tags()`:

```python
def _build_raw_object_path(import_date: str, shard_index: int, image_id: str, source_file_name: str) -> str:
    """生成 raw 图片在受管 storage 中的日期分片路径。"""
    extension = Path(source_file_name).suffix.lower()
    return f"images/raw/{import_date}/shard_{shard_index:03d}/{image_id}{extension}"
```

- [ ] **Step 6: Run pipeline tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/importers/test_import_pipeline.py -q
```

Expected: PASS.

## Task 3: Validation

- [ ] **Step 1: Run importer test suite**

Run:

```bash
.venv/bin/python -m pytest tests/unit/importers -q
```

Expected: PASS.

- [ ] **Step 2: Run project quality checks**

Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m mypy src/image_gallery
```

Expected: all pass.

- [ ] **Step 3: Rerun the local importer notebook flow as a script**

Run a Python script equivalent to the notebook:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import pandas as pd
from image_gallery.dataset import Dataset
from image_gallery.importers import ImportPipeline, LocalDirectoryReader
from image_gallery.storage import FileSystemStorage

repo_root = Path.cwd()
source_dir = Path('/mnt/c/Users/wuchaoli/Pictures/测试图片')
library_root = repo_root / 'notebooks' / '.importers_test_library'
storage = FileSystemStorage(storage_name='test_picture_library').connect(root=library_root / 'storage')
records = LocalDirectoryReader(source_dir).read()
result = ImportPipeline(
    storage=storage,
    output_dir=library_root / 'outputs',
    global_tags=['dataset/test_pictures', 'source/windows_pictures'],
).run(records)
raw_dataset = Dataset.from_path(result.raw_dataset_path)
failure_path = Path(result.failure_manifest_path)
failure_frame = pd.read_json(failure_path, lines=True) if failure_path.stat().st_size else pd.DataFrame()
print('source_records:', len(records))
print('report:', result.report)
print('raw_count:', raw_dataset.count())
print('failure_count:', len(failure_frame))
print(raw_dataset.to_frame()['image_uri'].head().to_string(index=False))
PY
```

Expected: 33 source records, 33 successes, 0 failures, and printed `image_uri` paths containing `images/raw/<yyyy-mm-dd>/shard_001/<uuid>.<ext>`.

## Task 4: Commit

- [ ] **Step 1: Review diff**

Run:

```bash
git diff -- src/image_gallery/importers/pipeline.py tests/unit/importers/test_import_pipeline.py
```

Expected: only pipeline path logic and pipeline tests changed.

- [ ] **Step 2: Commit implementation**

Run:

```bash
git add src/image_gallery/importers/pipeline.py tests/unit/importers/test_import_pipeline.py docs/superpowers/plans/2026-07-02-import-path-sharding.md
git commit -m "feat: shard imported image paths"
```

Expected: commit succeeds. Do not include unrelated existing notebook or `.gitignore` changes unless explicitly requested.
