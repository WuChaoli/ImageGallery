# Task 8 Report

## Status

DONE

## Scope delivered

- Added `tests/integration/cleaning/test_cleaner_runtime_resume.py` to cover:
  - resume by `run_id`
  - resume by `CleanerResult`
  - dataset fingerprint validation
  - plan hash validation
  - sample rule validation
  - evaluation-only rerun
  - rejection when parameter computer config changes
- Updated `tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py` to the Task 7+/Task 8 `CleanerExecution -> CleanerResult` API.
- Implemented runtime resume validation against persisted run metadata and persisted graph nodes.
- Implemented evaluation-only rerun that reuses persisted parameter tables/artifacts and only re-evaluates operators plus final merge.
- Persisted parameter computer config hashes into `state.json`.
- Added relation manifest writing in the scheduler and semantic artifact manifest wiring so semantic embeddings/index/relation can be validated during reuse.

## Files changed

- `src/image_gallery/cleaning/basic.py`
- `src/image_gallery/cleaning/execution.py`
- `src/image_gallery/cleaning/runtime.py`
- `src/image_gallery/cleaning/runtime_state.py`
- `src/image_gallery/cleaning/scheduler.py`
- `src/image_gallery/operators/computers/semantic.py`
- `tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py`
- `tests/integration/cleaning/test_cleaner_runtime_resume.py`

## Validation

### Required pytest

```bash
/home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/integration/cleaning/test_cleaner_runtime_resume.py tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py -q
```

Result: `8 passed in 4.73s`

### Ruff

```bash
/home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m ruff check src/image_gallery/cleaning/runtime.py src/image_gallery/cleaning/execution.py src/image_gallery/cleaning/scheduler.py src/image_gallery/cleaning/runtime_state.py src/image_gallery/cleaning/basic.py src/image_gallery/operators/computers/semantic.py tests/integration/cleaning/test_cleaner_runtime_resume.py tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py
```

Result: `All checks passed!`

### Mypy

```bash
/home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m mypy src/image_gallery/cleaning/runtime.py src/image_gallery/cleaning/execution.py src/image_gallery/cleaning/scheduler.py src/image_gallery/cleaning/runtime_state.py src/image_gallery/cleaning/basic.py src/image_gallery/operators/computers/semantic.py
```

Result: `Success: no issues found in 6 source files`

## Notes

- `CleanerResult` still does not expose public `cache_root` / `work_dir`; rerun/resume resolve internals through private runtime state only.
- Rerun is intentionally limited to evaluation-only compatibility. Any parameter node config drift or graph-shape drift is rejected.
