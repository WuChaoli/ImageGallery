# Cleaner Runtime StateGraph Real Test Checklist

## Required Commands

```bash
.venv/bin/python -m pytest -s tests/integration/cleaning/test_cleaner_runtime_stategraph_real_dataset.py -q
.venv/bin/python -m pytest -s tests/integration/cleaning/test_cleaner_runtime_resume.py tests/integration/cleaning/test_basic_cleaner_rerun.py -q
.venv/bin/python -m pytest -s tests/integration/cleaning/test_cleaner_runtime_toml.py -q
.venv/bin/python -m pytest -s tests/unit/cleaning tests/unit/operators -q
.venv/bin/python -m pytest -s tests/integration/cleaning -q
.venv/bin/python -m jupyter nbconvert --to notebook --execute notebooks/cleaner_runtime_stategraph_real_test.ipynb --inplace
.venv/bin/python -m ruff check src tests notebooks/_helpers
.venv/bin/python -m mypy src/image_gallery
```

If `jupyter-nbconvert` is unavailable but `nbclient` is installed, run the equivalent execution path:

```bash
mkdir -p .tmp/jupyter-runtime .tmp/tmp
TMPDIR=/home/wuchaoli/codespace/ImageGallery/.tmp/tmp \
JUPYTER_RUNTIME_DIR=/home/wuchaoli/codespace/ImageGallery/.tmp/jupyter-runtime \
.venv/bin/python - <<'PY'
from pathlib import Path
import nbformat
from nbclient import NotebookClient

path = Path("notebooks/cleaner_runtime_stategraph_real_test.ipynb")
notebook = nbformat.read(path, as_version=4)
client = NotebookClient(
    notebook,
    timeout=1200,
    kernel_name="python3",
    resources={"metadata": {"path": str(Path.cwd())}},
)
client.execute()
nbformat.write(notebook, path)
print(f"executed {path}")
PY
```

## Required Evidence

- `sample_1000` raw frame row count is 1000.
- `BasicCleaner(...).compile().dry_run(sample_1000)` has no errors.
- The compiled graph contains at least one `parameter.*` node, all expected `evaluation.*` nodes, and `merge.final_action`.
- Runtime result status is `completed`.
- Exported parameter and evaluation tables both have 1000 rows.
- `final_action` contains only `keep`, `drop`, and `review`.
- `full` export row count equals `clean + review + dropped`.
- SQLite `cleaning_run.status` is `completed`.
- All SQLite `graph_node` rows are `completed`.
- SQLite `run_event` has at least one event.
- `execution_plan.json`, `artifacts.json`, and debug bundle are exported through `CleanerResult`.
- Overall and operator preview HTML files are written and contain valid HTML structure.
- Completed `resume()` returns the same run id and remains `completed`.
- TOML recipe can run on the same real dataset.

## Environment Notes

- The real dataset tests must load data through `notebooks/_helpers/datasets.py`.
- If `datasets/sample_1000/raw.parquet` or MinIO image access is unavailable, the real dataset tests should be skipped with an explicit reason.
- Use `-s` when running pytest in this workspace if pytest capture raises a temporary file `FileNotFoundError`.
- In WSL, set `TMPDIR` and `JUPYTER_RUNTIME_DIR` to Linux filesystem paths if Jupyter kernel startup writes connection files under `/mnt/c/.../Temp`.
