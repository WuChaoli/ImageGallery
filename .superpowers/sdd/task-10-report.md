# Task 10 Report: Verification Gate and Compatibility Cleanup

## Scope

Task 10 completed the cleaner runtime migration cleanup around the canonical lifecycle:

- `BasicCleaner(...).compile()` remains the builder entry and returns `CleanerExecution`.
- `BasicCleaner(...).run(dataset, ...)` remains the shortcut runner and returns `CleanerResult`.
- Direct result-reader compatibility was removed from `BasicCleaner` and its abstract base.
- Result consumption was migrated to `CleanerResult` across affected integration tests and examples.
- `CleanerResult` cache root stayed private; examples now export public artifacts instead of reading internal paths.

## Files Changed

- `src/image_gallery/cleaning/cleaner.py`
- `src/image_gallery/cleaning/basic.py`
- `src/image_gallery/cleaning/execution.py`
- `tests/unit/cleaning/test_basic_cleaner.py`
- `tests/integration/cleaning/test_basic_cleaner_builtin_run.py`
- `tests/integration/cleaning/test_basic_cleaner_export.py`
- `tests/integration/cleaning/test_basic_cleaner_minimal_run.py`
- `tests/integration/cleaning/test_basic_cleaner_remote_dataset.py`
- `tests/integration/cleaning/test_basic_cleaner_rerun.py`
- `examples/generate_light_quality_operator_previews.py`
- `examples/stage4_basic_cleaner_quickstart.py`

## Change Summary

### 1. Builder/result boundary cleanup

- Removed stale reader methods from `Cleaner` / `BasicCleaner`:
  - `preview`
  - `preview_html`
  - `state`
  - `rerun`
  - `result`
  - `export`
- Added a unit test to lock the new surface: `BasicCleaner` now exposes builder lifecycle only.

### 2. Result lifecycle migration

- Updated integration tests to use:
  - `result = cleaner.run(...)`
  - `result.export(...)`
  - `result.preview(...)`
  - `result.preview_html(...)`
  - `result.state()`
  - `result.result(...)`
- Updated rerun coverage to use the canonical execution path:
  - `execution = cleaner.compile()`
  - `rerun_result = execution.rerun(result, operators=[...])`

### 3. Run output directory compatibility

- Preserved `run(output_dir=...)` behavior in `CleanerExecution.run()` so existing verification flows that inspect runtime artifacts under a provided directory continue to work.
- Added type validation for `output_dir`.

### 4. Example cleanup

- Migrated example preview/export usage from `BasicCleaner` to `CleanerResult`.
- Removed example access to internal runtime paths and replaced it with public `export_table(...)` outputs plus `run_id`.

## Verification Outcomes

### Command 1

```bash
/home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/cleaning tests/unit/operators -q
```

Result: PASS

- `137 passed in 1.35s`

### Command 2

```bash
/home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/integration/cleaning -q
```

Result: PASS

- `28 passed, 1 skipped in 11.23s`

### Command 3

```bash
/home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/notebooks -q
```

Result: PASS

- `13 passed, 2 skipped in 0.55s`
- Fallback rerun after notebook smoke failure: `13 passed, 2 skipped in 0.42s`

### Command 4

```bash
/home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m ruff check src tests
```

Result: PASS

- `All checks passed!`

Note: I also ran `ruff check src tests examples` after updating examples; that passed too.

### Command 5

```bash
/home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m mypy src/image_gallery
```

Result: PASS

- `Success: no issues found in 67 source files`

### Command 6

```bash
PYTHONPATH=src:. /home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py -q
```

Result: PASS

- `3 passed in 4.98s`

### Command 7

```bash
/home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m jupyter nbconvert --to notebook --execute notebooks/cleaning_v3_sample_1000_test.ipynb --inplace
```

Result: FAILED DUE TO ENVIRONMENT

Exact stderr/stdout:

```text
usage: jupyter.py [-h] [--version] [--config-dir] [--data-dir] [--runtime-dir]
                  [--paths] [--json] [--debug]
                  [subcommand]

Jupyter: Interactive Computing

positional arguments:
  subcommand     the subcommand to launch

options:
  -h, --help     show this help message and exit
  --version      show the versions of core jupyter packages and exit
  --config-dir   show Jupyter config dir
  --data-dir     show Jupyter data dir
  --runtime-dir  show Jupyter runtime dir
  --paths        show all Jupyter paths. Add --json for machine-readable
                 format.
  --json         output paths as machine-readable json
  --debug        output debug information about paths

Available subcommands: kernel kernelspec migrate run troubleshoot

Jupyter command `jupyter-nbconvert` not found.
```

Closest pytest substitute executed per brief:

```bash
/home/wuchaoli/codespace/ImageGallery/.venv/bin/python -m pytest tests/unit/notebooks -q
```

Result: PASS

- `13 passed, 2 skipped in 0.42s`

## Final Status

- Cleaner runtime migration verification gate is complete.
- Canonical lifecycle is enforced in tests and examples.
- Notebook smoke could not execute because `jupyter-nbconvert` is unavailable in the current environment.

## Fix pass

- Updated `notebooks/operators_phash_duplicate_test.ipynb` to use `execution = BasicCleaner(...).compile()`, `result = execution.run(...)`, and `result.export(...)` / `result.preview_html(...)`.
- Cleared notebook outputs to avoid stale runtime path leakage.

### Fix validation

- `pytest tests/unit/notebooks -q`: `13 passed, 2 skipped`
- `ruff check src tests examples`: `All checks passed!`
- `mypy src/image_gallery`: `Success: no issues found in 67 source files`

## Fix pass 2

- Replaced the remaining `cleaner.plan()` reference in `notebooks/operators_phash_duplicate_test.ipynb` with `execution.plan()`.
- Re-cleared notebook outputs.

### Fix validation 2

- `rg` check found no `cleaner.` / runtime cache path remnants in `notebooks/operators_phash_duplicate_test.ipynb`.
- `pytest tests/unit/notebooks -q`: `13 passed, 2 skipped`
- `ruff check src tests examples notebooks/_helpers`: `All checks passed!`
- `mypy src/image_gallery`: `Success: no issues found in 67 source files`

## Fix pass 3

- Added `CleanerResult.export_relation(relation_name, path)` as a read-only relation export surface.
- Updated `notebooks/operators_phash_duplicate_test.ipynb` to export parameter/evaluation/relation tables through `CleanerResult` instead of discovering and reading the internal run directory.
- Re-cleared notebook outputs.

### Fix validation 3

- `rg` check found no `run_dir` / runtime cache path / direct relation-path reads in `notebooks/operators_phash_duplicate_test.ipynb`.
- `pytest tests/unit/cleaning/test_result.py tests/unit/notebooks -q`: `21 passed, 2 skipped`
- `pytest tests/integration/cleaning -q`: `28 passed, 1 skipped`
- `ruff check src tests examples notebooks/_helpers`: `All checks passed!`
- `mypy src/image_gallery`: `Success: no issues found in 67 source files`

## Final review fix pass

- Tightened resume/rerun output validation so graph-consumed parameters must exist in both `parameter_table.parquet` and `parameter_manifest.json`; missing manifest entries now fail resume.
- Derived expected parameter ownership from graph node required-parameter consumption instead of full computer capability.
- Added read-only `CleanerResult.export_relations(...)` and `CleanerResult.export_debug_bundle(...)` to complete the planned public export surface.
- Added unit and integration regressions for relation/debug exports and missing parameter manifest entries.

### Final review fix validation

- `pytest tests/integration/cleaning/test_cleaner_runtime_resume.py tests/unit/cleaning/test_result.py -q`: `20 passed`
- `pytest tests/integration/cleaning -q`: `29 passed, 1 skipped`
- `ruff check src tests examples notebooks/_helpers`: `All checks passed!`
- `mypy src/image_gallery`: `Success: no issues found in 67 source files`
