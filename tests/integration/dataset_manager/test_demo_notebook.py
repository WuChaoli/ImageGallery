import json
from pathlib import Path
from typing import cast

import pytest
from examples.dataset_manager_demo.helpers import DemoBackendSession, stop_demo_backend


@pytest.mark.dataset_backend
def test_dataset_manager_demo_notebook_runs_managed_path() -> None:
    """从干净 namespace 执行 Notebook 的显式 managed Backend 路径。"""
    notebook = json.loads(Path("examples/dataset_manager_demo/dataset_manager_demo.ipynb").read_text(encoding="utf-8"))
    namespace: dict[str, object] = {}
    try:
        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] != "code":
                continue
            source = "".join(cell["source"]).replace(
                "# demo_backend = start_demo_backend(demo_root=DEMO_ROOT / 'runtime', recreate=True)",
                "demo_backend = start_demo_backend(demo_root=DEMO_ROOT / 'runtime', recreate=True)",
            )
            # Notebook 单元本身就是待验证的可执行输入，并且文件固定在仓库中而非来自用户。
            exec(compile(source, f"<dataset-manager-demo-{index}>", "exec"), namespace)  # noqa: S102
    finally:
        for name in ("manager", "storage"):
            resource = namespace.get(name)
            close = getattr(resource, "close", None)
            if callable(close):
                close()
        backend = namespace.get("demo_backend")
        if backend is not None and getattr(backend, "resources", []):
            stop_demo_backend(cast(DemoBackendSession, backend), remove_volumes=True)
