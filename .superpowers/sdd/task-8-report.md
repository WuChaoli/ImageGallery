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

## Fix pass

- Tightened tracked artifact validation so resume/rerun now require manifests for tracked artifact refs, and expected `config_hash` values must exist and match.
- Persisted graph-node completion status during planned execution, then taught unfinished-run resume to reload persisted parameter outputs and skip already completed parameter nodes.
- Added regressions for:
  - missing semantic embedding manifest on resume
  - missing semantic index `config_hash` on rerun
  - unfinished-run resume reusing a completed parameter node without recomputation

### Fix validation

- `pytest`: `11 passed in 4.43s`
- `ruff`: `All checks passed!`
- `mypy`: `Success: no issues found in 3 source files`

## Fix pass 2

- 将 resume/rerun 的 trusted parameter config hash 来源改为已通过 `_validate_graph_nodes()` 校验的 persisted graph nodes，不再信任 `state.json` 或 `parameter_manifest.json` 中自报的 expected hash。
- 新增 state/parameter manifest/tracked artifact manifest/relation manifest 的 graph-anchored config hash 校验，阻断“同时篡改 state + manifests 形成自洽 stale hash”后仍可 resume 的路径。
- 对有明确 parameter computer owner 的 tracked artifact / relation / parameter manifest 强制要求可匹配的 `config_hash`；缺失或不匹配都会失败。
- 添加 semantic resume 回归测试，覆盖 embedding/index/relation manifests 与 `state.json`、`parameter_manifest.json` 同步篡改为 stale hash 的场景。

### Fix validation 2

- `pytest`: `12 passed in 5.79s`
- `ruff`: `All checks passed!`
- `mypy`: `Success: no issues found in 1 source file`
