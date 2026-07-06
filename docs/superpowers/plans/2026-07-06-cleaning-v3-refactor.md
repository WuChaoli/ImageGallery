# Cleaning V3 重构实施计划

> **给 agentic workers 的要求：** 实施本计划时必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，并按任务逐项执行。步骤使用复选框（`- [ ]`）跟踪进度。

**目标：** 将清洗平台从 v2 的 `BackendAdapter` 执行模型破坏性重构为 v3 的 `ParameterComputer + LogicalOperatorSpec + ImageBatch` 模型，并用 `format.decode_check` 与 `size.dimension_check` 验证最小闭环。

**架构：** 保持 `BasicCleaner([{operator_name: config}, ...])` 用户入口不变。Cleaner 先按逻辑算子收集参数需求，再按阶段执行 `ParameterComputer`：图片批次阶段由 Cleaner 统一读取与解码图片，形成共享 `ImageBatch`，多个 computer 只消费这个批次上下文，不各自读取图片；评估阶段只读 `parameter_table` 生成 `evaluation_table`。

**技术栈：** Python 3.10、pandas、pyarrow、Pillow、pytest、现有 `Dataset`、`BasicCleaner`、Parquet 表产物。

---

## 范围

本计划实现 v3 第一条破坏性重构切片：

1. 删除旧 `BackendAdapter` 模型、旧 `operators/backends/` 实现与对应测试。
2. 删除 fastdup 相关实现、注册项和测试，不保留兼容路径。
3. 新增 `ParameterComputer` 契约和 `ImageBatch` 共享读取/解码上下文。
4. 将 `OperatorSpec` 改为声明 `required_parameters`，不再声明 `backend_name`。
5. 将 `OperatorRegistry` 改为注册逻辑算子和参数计算单元。
6. 将 `BasicCleaner` 改为三阶段：image batch 参数计算 -> table/global 参数计算 -> evaluation。
7. 第一批只实现 `image_metadata_computer`。
8. 第一批只启用两个逻辑算子：
   - `format.decode_check`
   - `size.dimension_check`
9. `rerun()` 第一版即遵守 v3 语义：只改评估配置时只重算 evaluation，不重算参数。

本计划不实现质量算子、hash、重复分组、near duplicate、聚类、离群、Notebook UI 或报告渲染。它们必须在 v3 底层契约稳定后用独立切片实现。

## 当前状态

当前代码仍然是 v2 模型：

- `src/image_gallery/operators/spec.py` 中有 `OperatorSpec.backend_name`。
- `src/image_gallery/operators/registry.py` 同时注册 `OperatorSpec` 和 `BackendAdapter`。
- `src/image_gallery/operators/backends/base.py` 定义 `BackendAdapter`、`BackendOperatorRequest` 和 `BackendResult`。
- `src/image_gallery/cleaning/basic.py` 按 backend name 对逻辑算子分组。
- `src/image_gallery/operators/builtin.py` 注册 Pillow、OpenCV、hash 和 fastdup backend。

v3 目标以 `docs/architecture/modules/清洗平台与算子库-v3.md` 为准。

## 文件结构

新增：

```text
src/image_gallery/operators/computers/
  __init__.py
  base.py
  metadata.py

tests/unit/operators/
  test_parameter_computer_contract.py
  test_metadata_computer.py
```

修改：

```text
src/image_gallery/operators/spec.py
src/image_gallery/operators/registry.py
src/image_gallery/operators/builtin.py
src/image_gallery/cleaning/basic.py
tests/unit/operators/test_operator_specs.py
tests/unit/operators/test_registry.py
tests/unit/operators/test_builtin_specs.py
tests/unit/cleaning/test_basic_cleaner.py
tests/integration/cleaning/test_basic_cleaner_builtin_run.py
tests/integration/cleaning/test_basic_cleaner_export.py
tests/integration/cleaning/test_basic_cleaner_rerun.py
```

删除：

```text
src/image_gallery/operators/backends/
tests/unit/operators/test_backend_contract.py
tests/unit/operators/test_fastdup_backend.py
tests/unit/operators/test_pillow_backend.py
tests/unit/operators/test_opencv_backend.py
tests/unit/operators/test_hash_backend.py
```

本计划不保留旧 backend 和旧 backend 测试。所有默认执行路径必须迁移到 `ParameterComputer`。

---

## Task 1：建立基线并删除旧 Backend 模型

**Files:**
- Delete: `src/image_gallery/operators/backends/`
- Delete: `tests/unit/operators/test_backend_contract.py`
- Delete: `tests/unit/operators/test_fastdup_backend.py`
- Delete: `tests/unit/operators/test_pillow_backend.py`
- Delete: `tests/unit/operators/test_opencv_backend.py`
- Delete: `tests/unit/operators/test_hash_backend.py`
- Modify: `src/image_gallery/operators/builtin.py`
- Test: `tests/unit/operators/test_builtin_specs.py`

- [ ] **Step 1：运行当前聚焦基线**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators tests/unit/cleaning tests/integration/cleaning -q
```

Expected：记录当前 v2 失败/通过状态。后续失败应来自本次破坏性迁移，不应来自无关模块。

- [ ] **Step 2：编写失败测试，确认默认 registry 不再暴露旧 backend 和 fastdup**

修改 `tests/unit/operators/test_builtin_specs.py`：

```python
from image_gallery.operators.builtin import create_default_registry


def test_default_registry_contains_only_first_v3_operators() -> None:
    registry = create_default_registry()

    assert registry.list_operators() == [
        "format.decode_check",
        "size.dimension_check",
    ]


def test_default_registry_excludes_fastdup_and_near_duplicate() -> None:
    registry = create_default_registry()

    assert "duplicate.near_duplicate_check" not in registry.list_operators()
```

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_builtin_specs.py -q
```

Expected：FAIL，因为当前 registry 仍注册多个 v2 算子与 backend。

- [ ] **Step 3：删除旧 backend 目录与测试**

Run:

```bash
git rm -r src/image_gallery/operators/backends
git rm tests/unit/operators/test_backend_contract.py tests/unit/operators/test_fastdup_backend.py tests/unit/operators/test_pillow_backend.py tests/unit/operators/test_opencv_backend.py tests/unit/operators/test_hash_backend.py
```

Expected：旧 backend 实现和测试从 Git 中删除。

- [ ] **Step 4：临时收敛 builtin registry**

修改 `src/image_gallery/operators/builtin.py`，删除所有旧 backend import，先保留 evaluator 函数，`create_default_registry()` 暂时只注册逻辑算子：

```python
import pandas as pd

from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


def create_default_registry() -> OperatorRegistry:
    """创建第一版 v3 逻辑算子注册表。"""
    registry = OperatorRegistry()
    for spec in _builtin_specs():
        registry.register_operator(spec)
    return registry
```

`_builtin_specs()` 暂时只保留：

```text
format.decode_check
size.dimension_check
```

Expected：此时 tests 仍可能因为 `OperatorSpec` 还未迁移而失败，下一任务修复。

- [ ] **Step 5：提交**

```bash
git add src/image_gallery/operators tests/unit/operators
git commit -m "refactor: remove legacy cleaning backends"
```

---

## Task 2：新增 ParameterComputer 与 ImageBatch 契约

**Files:**
- Create: `src/image_gallery/operators/computers/__init__.py`
- Create: `src/image_gallery/operators/computers/base.py`
- Test: `tests/unit/operators/test_parameter_computer_contract.py`

- [ ] **Step 1：编写失败的契约测试**

创建 `tests/unit/operators/test_parameter_computer_contract.py`：

```python
from pathlib import Path

import pandas as pd

from image_gallery.operators.computers.base import (
    ComputeStage,
    ImageBatch,
    ImageBatchItem,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)


class DemoComputer(ParameterComputer):
    name = "demo_computer"
    stage = ComputeStage.IMAGE_BATCH
    produced_parameters = frozenset({"demo_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        assert request.image_batch is not None
        return ParameterResult(
            parameter_updates=pd.DataFrame(
                {
                    "image_id": [item.image_id for item in request.image_batch.items],
                    "demo_score": [1.0 for _ in request.image_batch.items],
                }
            ),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={
                "demo_score": {
                    "computer": self.name,
                    "stage": self.stage.value,
                    "config_hash": request.config_hash,
                }
            },
        )


def test_parameter_computer_contract_uses_shared_image_batch(tmp_path: Path) -> None:
    image_batch = ImageBatch(
        items=[
            ImageBatchItem(
                image_id="img-1",
                image_uri="/tmp/img-1.png",
                row={"image_id": "img-1", "image_uri": "/tmp/img-1.png"},
                data=b"fake",
                image=None,
                error=None,
            )
        ]
    )
    request = ParameterRequest(
        parameter_table=pd.DataFrame({"image_id": ["img-1"], "image_uri": ["/tmp/img-1.png"]}),
        requested_parameters=frozenset({"demo_score"}),
        config={},
        config_hash="abc123",
        artifacts_dir=tmp_path,
        image_batch=image_batch,
    )

    result = DemoComputer().compute(request)

    assert result.parameter_updates.to_dict(orient="records") == [
        {"image_id": "img-1", "demo_score": 1.0}
    ]
    assert result.parameter_manifest["demo_score"]["computer"] == "demo_computer"
```

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_parameter_computer_contract.py -q
```

Expected：FAIL，因为 `image_gallery.operators.computers.base` 不存在。

- [ ] **Step 2：实现契约类型**

创建 `src/image_gallery/operators/computers/base.py`：

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pandas as pd
from PIL import Image


class ComputeStage(str, Enum):
    """参数计算阶段。"""

    IMAGE_BATCH = "image_batch"
    TABLE_DERIVED = "table_derived"
    DATASET_GLOBAL = "dataset_global"


@dataclass(frozen=True)
class ImageBatchItem:
    """Cleaner 统一读取和解码后的单张图片上下文。"""

    image_id: str
    image_uri: str
    row: dict[str, object]
    data: bytes | None
    image: Image.Image | None
    error: str | None


@dataclass(frozen=True)
class ImageBatch:
    """同一批图片的共享读取/解码上下文。"""

    items: list[ImageBatchItem]


@dataclass(frozen=True)
class ParameterRequest:
    """一次参数计算请求。"""

    parameter_table: pd.DataFrame
    requested_parameters: frozenset[str]
    config: dict[str, object]
    config_hash: str
    artifacts_dir: Path
    image_batch: ImageBatch | None = None


@dataclass(frozen=True)
class ParameterResult:
    """参数计算结果。"""

    parameter_updates: pd.DataFrame
    relation_updates: dict[str, pd.DataFrame]
    artifact_refs: dict[str, str]
    parameter_manifest: dict[str, dict[str, object]]


class ParameterComputer(ABC):
    """参数计算单元基类。"""

    name: str
    stage: ComputeStage
    produced_parameters: frozenset[str]

    @abstractmethod
    def compute(self, request: ParameterRequest) -> ParameterResult:
        """按请求批量生产参数列。"""
```

创建 `src/image_gallery/operators/computers/__init__.py`：

```python
from image_gallery.operators.computers.base import (
    ComputeStage,
    ImageBatch,
    ImageBatchItem,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)

__all__ = [
    "ComputeStage",
    "ImageBatch",
    "ImageBatchItem",
    "ParameterComputer",
    "ParameterRequest",
    "ParameterResult",
]
```

- [ ] **Step 3：运行契约测试**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_parameter_computer_contract.py -q
```

Expected：PASS。

- [ ] **Step 4：提交**

```bash
git add src/image_gallery/operators/computers tests/unit/operators/test_parameter_computer_contract.py
git commit -m "feat: add image batch parameter computer contract"
```

---

## Task 3：迁移逻辑算子规格与 Registry

**Files:**
- Modify: `src/image_gallery/operators/spec.py`
- Modify: `src/image_gallery/operators/registry.py`
- Test: `tests/unit/operators/test_operator_specs.py`
- Test: `tests/unit/operators/test_registry.py`

- [ ] **Step 1：编写失败测试，验证 `required_parameters`**

修改 `tests/unit/operators/test_operator_specs.py`：

```python
import pandas as pd
import pytest

from image_gallery.operators.spec import OperatorSpec


def test_operator_spec_evaluates_declared_columns() -> None:
    spec = OperatorSpec(
        name="quality.demo_check",
        category="quality",
        required_parameters=["demo_score"],
        evaluation_columns=["demo_score", "demo_action", "demo_reason"],
        default_config={"threshold": 0.5, "action": "review"},
        action_column="demo_action",
        reason_column="demo_reason",
        evaluator=lambda parameter_table, config: pd.DataFrame(
            {
                "image_id": parameter_table["image_id"],
                "demo_score": parameter_table["demo_score"],
                "demo_action": "keep",
                "demo_reason": "",
            }
        ),
    )

    result = spec.evaluate(
        pd.DataFrame({"image_id": ["img-1"], "demo_score": [0.1]}),
        {"threshold": 0.5, "action": "review"},
    )

    assert result.columns.tolist() == ["image_id", "demo_score", "demo_action", "demo_reason"]
    assert spec.required_parameters == ["demo_score"]


def test_operator_spec_rejects_missing_required_parameters() -> None:
    spec = OperatorSpec(
        name="quality.demo_check",
        category="quality",
        required_parameters=["demo_score"],
        evaluation_columns=["demo_action", "demo_reason"],
        default_config={"action": "review"},
        action_column="demo_action",
        reason_column="demo_reason",
        evaluator=lambda parameter_table, config: pd.DataFrame(),
    )

    with pytest.raises(ValueError, match="missing required parameters"):
        spec.evaluate(pd.DataFrame({"image_id": ["img-1"]}), {"action": "review"})
```

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_operator_specs.py -q
```

Expected：FAIL，因为当前 `OperatorSpec` 仍要求 `backend_name`。

- [ ] **Step 2：更新 OperatorSpec**

修改 `src/image_gallery/operators/spec.py`：

```python
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class OperatorSpec:
    """逻辑算子规格，描述参数需求和评估输出契约。"""

    name: str
    category: str
    required_parameters: list[str]
    evaluation_columns: list[str]
    default_config: dict[str, object]
    action_column: str
    reason_column: str
    evaluator: Callable[[pd.DataFrame, dict[str, object]], pd.DataFrame]

    def evaluate(self, parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
        """基于参数表和配置生成该算子的 evaluation 列。"""
        missing_parameters = [column for column in self.required_parameters if column not in parameter_table.columns]
        if missing_parameters:
            raise ValueError(f"missing required parameters for {self.name}: {missing_parameters}")

        result = self.evaluator(parameter_table.copy(), config)
        required_columns = ["image_id", *self.evaluation_columns]
        missing_columns = [column for column in required_columns if column not in result.columns]
        if missing_columns:
            raise ValueError(f"missing evaluation columns for {self.name}: {missing_columns}")
        return result[required_columns].copy()
```

- [ ] **Step 3：编写失败测试，验证 registry 支持参数计算单元**

修改 `tests/unit/operators/test_registry.py`：

```python
import pandas as pd
import pytest

from image_gallery.cleaning.errors import UnknownOperatorError
from image_gallery.operators.computers.base import (
    ComputeStage,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


class DemoComputer(ParameterComputer):
    name = "demo_computer"
    stage = ComputeStage.IMAGE_BATCH
    produced_parameters = frozenset({"demo_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(
            parameter_updates=pd.DataFrame({"image_id": request.parameter_table["image_id"], "demo_score": [1.0]}),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={},
        )


def _evaluate(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "demo_action": config["action"],
            "demo_reason": "ok",
        }
    )


def test_registry_resolves_operator_and_parameter_computer() -> None:
    registry = OperatorRegistry()
    computer = DemoComputer()
    spec = OperatorSpec(
        name="quality.demo_check",
        category="quality",
        required_parameters=["demo_score"],
        evaluation_columns=["demo_action", "demo_reason"],
        default_config={"action": "review"},
        action_column="demo_action",
        reason_column="demo_reason",
        evaluator=_evaluate,
    )

    registry.register_parameter_computer(computer)
    registry.register_operator(spec)

    assert registry.get_operator("quality.demo_check") is spec
    assert registry.get_parameter_computer("demo_computer") is computer
    assert registry.find_computers_for_parameters({"demo_score"}) == [computer]
    assert registry.list_operators() == ["quality.demo_check"]


def test_registry_rejects_missing_parameter_producer() -> None:
    registry = OperatorRegistry()

    with pytest.raises(UnknownOperatorError, match="missing parameter producers"):
        registry.find_computers_for_parameters({"missing_score"})
```

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_registry.py -q
```

Expected：FAIL，因为 `OperatorRegistry` 还不支持 parameter computer。

- [ ] **Step 4：更新 OperatorRegistry**

修改 `src/image_gallery/operators/registry.py`：

```python
from image_gallery.cleaning.errors import UnknownOperatorError
from image_gallery.operators.computers.base import ParameterComputer
from image_gallery.operators.spec import OperatorSpec


class OperatorRegistry:
    """逻辑算子和参数计算单元注册表。"""

    def __init__(self) -> None:
        self._operators: dict[str, OperatorSpec] = {}
        self._parameter_computers: dict[str, ParameterComputer] = {}

    def register_operator(self, spec: OperatorSpec) -> None:
        """注册逻辑算子。"""
        self._operators[spec.name] = spec

    def register_parameter_computer(self, computer: ParameterComputer) -> None:
        """注册参数计算单元。"""
        self._parameter_computers[computer.name] = computer

    def get_operator(self, operator_name: str) -> OperatorSpec:
        """按名称获取逻辑算子。"""
        try:
            return self._operators[operator_name]
        except KeyError as exc:
            raise UnknownOperatorError(f"unknown operator: {operator_name}") from exc

    def get_parameter_computer(self, computer_name: str) -> ParameterComputer:
        """按名称获取参数计算单元。"""
        try:
            return self._parameter_computers[computer_name]
        except KeyError as exc:
            raise UnknownOperatorError(f"unknown parameter computer: {computer_name}") from exc

    def list_operators(self) -> list[str]:
        """返回当前可用算子名称。"""
        return sorted(self._operators)

    def find_computers_for_parameters(self, parameter_names: set[str]) -> list[ParameterComputer]:
        """按参数需求返回可覆盖这些参数的计算单元。"""
        remaining = set(parameter_names)
        selected: list[ParameterComputer] = []
        for computer in self._parameter_computers.values():
            covered = remaining & set(computer.produced_parameters)
            if covered:
                selected.append(computer)
                remaining -= covered
        if remaining:
            raise UnknownOperatorError(f"missing parameter producers: {sorted(remaining)}")
        return selected
```

- [ ] **Step 5：运行算子规格与 registry 测试**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_operator_specs.py tests/unit/operators/test_registry.py -q
```

Expected：PASS。

- [ ] **Step 6：提交**

```bash
git add src/image_gallery/operators/spec.py src/image_gallery/operators/registry.py tests/unit/operators/test_operator_specs.py tests/unit/operators/test_registry.py
git commit -m "refactor: migrate operators to parameter requirements"
```

---

## Task 4：实现共享 ImageBatch 构建与 ImageMetadataComputer

**Files:**
- Create: `src/image_gallery/operators/computers/metadata.py`
- Modify: `src/image_gallery/operators/computers/__init__.py`
- Modify: `src/image_gallery/cleaning/basic.py`
- Test: `tests/unit/operators/test_metadata_computer.py`
- Test: `tests/unit/cleaning/test_basic_cleaner.py`

- [ ] **Step 1：编写 metadata computer 测试，确认它不读取 Dataset**

创建 `tests/unit/operators/test_metadata_computer.py`：

```python
import pandas as pd

from image_gallery.operators.computers.base import ImageBatch, ImageBatchItem, ParameterRequest
from image_gallery.operators.computers.metadata import ImageMetadataComputer


def test_metadata_computer_uses_shared_decoded_batch(tmp_path) -> None:
    class FakeImage:
        width = 8
        height = 6
        format = "PNG"

    batch = ImageBatch(
        items=[
            ImageBatchItem(
                image_id="img-1",
                image_uri="/tmp/ok.png",
                row={"image_id": "img-1", "image_uri": "/tmp/ok.png"},
                data=b"abc",
                image=FakeImage(),
                error=None,
            )
        ]
    )
    result = ImageMetadataComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["img-1"], "image_uri": ["/tmp/ok.png"]}),
            requested_parameters=frozenset({"decode_ok", "decode_error", "width", "height", "file_size"}),
            config={},
            config_hash="metadata-v1",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    assert result.parameter_updates.to_dict(orient="records") == [
        {
            "image_id": "img-1",
            "decode_error": "",
            "decode_ok": True,
            "file_size": 3,
            "height": 6,
            "width": 8,
        }
    ]


def test_metadata_computer_records_shared_decode_error(tmp_path) -> None:
    batch = ImageBatch(
        items=[
            ImageBatchItem(
                image_id="img-bad",
                image_uri="/tmp/bad.png",
                row={"image_id": "img-bad", "image_uri": "/tmp/bad.png"},
                data=None,
                image=None,
                error="cannot identify image file",
            )
        ]
    )
    result = ImageMetadataComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["img-bad"], "image_uri": ["/tmp/bad.png"]}),
            requested_parameters=frozenset({"decode_ok", "decode_error", "width", "height"}),
            config={},
            config_hash="metadata-v1",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    row = result.parameter_updates.to_dict(orient="records")[0]
    assert row["image_id"] == "img-bad"
    assert row["decode_ok"] is False
    assert row["decode_error"] == "cannot identify image file"
    assert pd.isna(row["width"])
    assert pd.isna(row["height"])
```

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_metadata_computer.py -q
```

Expected：FAIL，因为 `ImageMetadataComputer` 还不存在。

- [ ] **Step 2：实现 ImageMetadataComputer**

创建 `src/image_gallery/operators/computers/metadata.py`：

```python
import pandas as pd

from image_gallery.operators.computers.base import (
    ComputeStage,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)


class ImageMetadataComputer(ParameterComputer):
    """基于 Cleaner 共享 ImageBatch 生产解码与尺寸参数。"""

    name = "image_metadata_computer"
    stage = ComputeStage.IMAGE_BATCH
    produced_parameters = frozenset(
        {
            "width",
            "height",
            "format",
            "decode_ok",
            "decode_error",
            "file_size",
        }
    )

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """从共享 ImageBatch 中提取被请求的元数据参数。"""
        if request.image_batch is None:
            raise ValueError("ImageMetadataComputer requires image_batch")

        requested = set(request.requested_parameters)
        rows: list[dict[str, object]] = []
        for item in request.image_batch.items:
            values = self._values_for_item(item)
            row: dict[str, object] = {"image_id": item.image_id}
            for parameter in sorted(requested & set(self.produced_parameters)):
                row[parameter] = values[parameter]
            rows.append(row)

        manifest = {
            parameter: {
                "computer": self.name,
                "stage": self.stage.value,
                "config_hash": request.config_hash,
            }
            for parameter in sorted(requested & set(self.produced_parameters))
        }
        return ParameterResult(
            parameter_updates=pd.DataFrame(rows),
            relation_updates={},
            artifact_refs={},
            parameter_manifest=manifest,
        )

    def _values_for_item(self, item: object) -> dict[str, object]:
        """把单张共享图片上下文转换为元数据字段。"""
        image = getattr(item, "image")
        data = getattr(item, "data")
        error = getattr(item, "error")
        if error or image is None:
            return {
                "width": pd.NA,
                "height": pd.NA,
                "format": "",
                "decode_ok": False,
                "decode_error": str(error or "image decode failed"),
                "file_size": len(data) if data is not None else pd.NA,
            }
        return {
            "width": int(image.width),
            "height": int(image.height),
            "format": str(getattr(image, "format", "") or ""),
            "decode_ok": True,
            "decode_error": "",
            "file_size": len(data) if data is not None else pd.NA,
        }
```

更新 `src/image_gallery/operators/computers/__init__.py`，导出 `ImageMetadataComputer`。

- [ ] **Step 3：在 BasicCleaner 中新增共享 ImageBatch 构建**

在 `src/image_gallery/cleaning/basic.py` 中新增 imports：

```python
from io import BytesIO

from PIL import Image
```

新增 helper。注意：这里必须用 `read_image_bytes()` 读取一次 bytes，然后直接用 Pillow 从 bytes 解码；不能再调用 `Dataset.read_image()`，因为现有 `Dataset.read_image()` 内部也会读取 bytes。

```python
def _build_image_batch(self, parameter_table: pd.DataFrame) -> ImageBatch:
    """统一读取和解码当前 parameter_table 中的图片，供 image batch computers 共享。"""
    context, _, _ = self._require_run(allow_missing_state=True)
    items: list[ImageBatchItem] = []
    for row in parameter_table.to_dict(orient="records"):
        image_id = str(row["image_id"])
        image_uri = str(row["image_uri"])
        try:
            data = context.dataset.read_image_bytes(image_uri)
            with Image.open(BytesIO(data)) as opened:
                opened.load()
                image = opened.copy()
                image.format = opened.format
            items.append(
                ImageBatchItem(
                    image_id=image_id,
                    image_uri=image_uri,
                    row=row,
                    data=data,
                    image=image,
                    error=None,
                )
            )
        except Exception as exc:
            items.append(
                ImageBatchItem(
                    image_id=image_id,
                    image_uri=image_uri,
                    row=row,
                    data=None,
                    image=None,
                    error=str(exc),
                )
            )
    return ImageBatch(items=items)
```

本步骤只新增 helper，后续 Task 6 接入执行流。

- [ ] **Step 4：运行 metadata computer 测试**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_metadata_computer.py -q
```

Expected：PASS。

- [ ] **Step 5：提交**

```bash
git add src/image_gallery/operators/computers src/image_gallery/cleaning/basic.py tests/unit/operators/test_metadata_computer.py
git commit -m "feat: add shared image batch metadata computer"
```

---

## Task 5：将内置逻辑算子接入 ParameterComputer

**Files:**
- Modify: `src/image_gallery/operators/builtin.py`
- Test: `tests/unit/operators/test_builtin_specs.py`

- [ ] **Step 1：更新内置算子测试**

修改 `tests/unit/operators/test_builtin_specs.py`：

```python
from image_gallery.operators.builtin import create_default_registry


def test_default_registry_contains_only_first_v3_operators() -> None:
    registry = create_default_registry()

    assert registry.list_operators() == [
        "format.decode_check",
        "size.dimension_check",
    ]


def test_decode_and_dimension_specs_declare_required_parameters() -> None:
    registry = create_default_registry()

    decode_spec = registry.get_operator("format.decode_check")
    dimension_spec = registry.get_operator("size.dimension_check")

    assert decode_spec.required_parameters == ["decode_ok", "decode_error"]
    assert decode_spec.evaluation_columns == ["decode_action", "decode_reason"]
    assert dimension_spec.required_parameters == ["width", "height"]
    assert dimension_spec.evaluation_columns == ["dimension_action", "dimension_reason"]


def test_default_registry_can_find_metadata_computer_for_builtin_parameters() -> None:
    registry = create_default_registry()

    computers = registry.find_computers_for_parameters(
        {
            "decode_ok",
            "decode_error",
            "width",
            "height",
        }
    )

    assert [computer.name for computer in computers] == ["image_metadata_computer"]
```

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_builtin_specs.py -q
```

Expected：FAIL，直到 builtin registry 注册 `ImageMetadataComputer` 且 spec 使用 `required_parameters`。

- [ ] **Step 2：更新 builtin registry 和 specs**

修改 `src/image_gallery/operators/builtin.py`：

```python
import pandas as pd

from image_gallery.operators.computers.metadata import ImageMetadataComputer
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


def create_default_registry() -> OperatorRegistry:
    """创建包含第一版 v3 基础逻辑算子和参数计算单元的注册表。"""
    registry = OperatorRegistry()
    registry.register_parameter_computer(ImageMetadataComputer())
    for spec in _builtin_specs():
        registry.register_operator(spec)
    return registry


def _builtin_specs() -> list[OperatorSpec]:
    """返回第一批 v3 内置逻辑算子规格。"""
    return [
        OperatorSpec(
            name="format.decode_check",
            category="format",
            required_parameters=["decode_ok", "decode_error"],
            evaluation_columns=["decode_action", "decode_reason"],
            default_config={"action": "drop"},
            action_column="decode_action",
            reason_column="decode_reason",
            evaluator=evaluate_decode_check,
        ),
        OperatorSpec(
            name="size.dimension_check",
            category="size",
            required_parameters=["width", "height"],
            evaluation_columns=["dimension_action", "dimension_reason"],
            default_config={"min_width": 1, "min_height": 1, "action": "drop"},
            action_column="dimension_action",
            reason_column="dimension_reason",
            evaluator=evaluate_dimension_check,
        ),
    ]
```

保留：

```text
evaluate_decode_check
evaluate_dimension_check
_as_int
```

删除本文件中与本切片无关的 quality、duplicate、near duplicate evaluator。

- [ ] **Step 3：运行 builtin 测试**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_builtin_specs.py -q
```

Expected：PASS。

- [ ] **Step 4：提交**

```bash
git add src/image_gallery/operators/builtin.py tests/unit/operators/test_builtin_specs.py
git commit -m "feat: wire metadata operators to v3 registry"
```

---

## Task 6：重构 BasicCleaner 为三阶段执行

**Files:**
- Modify: `src/image_gallery/cleaning/basic.py`
- Test: `tests/unit/cleaning/test_basic_cleaner.py`

- [ ] **Step 1：把 fake backend 测试改为 fake parameter computer 测试**

修改 `tests/unit/cleaning/test_basic_cleaner.py`，用 `CountingComputer(ParameterComputer)` 替代 `CountingBackend(BackendAdapter)`。核心 fake：

```python
class CountingComputer(ParameterComputer):
    name = "counting_computer"
    stage = ComputeStage.IMAGE_BATCH
    produced_parameters = frozenset({"demo_score"})

    def __init__(self) -> None:
        self.calls: list[tuple[set[str], int]] = []

    def compute(self, request: ParameterRequest) -> ParameterResult:
        assert request.image_batch is not None
        self.calls.append((set(request.requested_parameters), len(request.image_batch.items)))
        return ParameterResult(
            parameter_updates=pd.DataFrame(
                {
                    "image_id": [item.image_id for item in request.image_batch.items],
                    "demo_score": [0.9, 0.2],
                }
            ),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={
                "demo_score": {
                    "computer": self.name,
                    "stage": self.stage.value,
                    "config_hash": request.config_hash,
                }
            },
        )
```

核心断言：

```python
assert computer.calls == [({"demo_score"}, 2)]
```

含义：两个逻辑算子共享同一次 image batch 参数计算，且 computer 消费共享 batch，不自己读取 Dataset。

- [ ] **Step 2：补充 ImageBatch 构建测试，验证每张图片只读取一次 bytes**

确保 `tests/unit/cleaning/test_basic_cleaner.py` 已导入：

```python
from PIL import Image
```

在测试文件中新增继承 `Dataset` 的测试替身：

```python
class CountingReadDataset(Dataset):
    def __init__(self, dataset_path: str, image_bytes: bytes) -> None:
        super().__init__(dataset_path=dataset_path)
        self.image_bytes = image_bytes
        self.read_calls: list[str] = []

    def read_image_bytes(self, image_uri: str) -> bytes:
        self.read_calls.append(image_uri)
        return self.image_bytes
```

新增测试：

```python
def test_basic_cleaner_builds_shared_image_batch_with_one_byte_read_per_image(tmp_path: Path) -> None:
    image_path = tmp_path / "image.png"
    Image.new("RGB", (4, 3), color=(255, 0, 0)).save(image_path, format="PNG")
    raw_path = tmp_path / "raw.parquet"
    pd.DataFrame(
        {
            "image_id": ["img-1"],
            "image_uri": [str(image_path)],
        }
    ).to_parquet(raw_path, index=False)
    dataset = CountingReadDataset(str(raw_path), image_path.read_bytes())
    cleaner = BasicCleaner([{"format.decode_check": {}}])
    cleaner.run(dataset, output_dir=tmp_path / "cleaning")

    assert dataset.read_calls == [str(image_path)]
```

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_basic_cleaner.py::test_basic_cleaner_builds_shared_image_batch_with_one_byte_read_per_image -q
```

Expected：FAIL，直到本任务后续步骤把 `BasicCleaner` 接入共享 `ImageBatch` 且不再调用 `Dataset.read_image()`。这个测试用于防止重新引入 `read_image_bytes()` + `read_image()` 双读。

- [ ] **Step 3：调整 `ResolvedOperatorRun`**

修改 `src/image_gallery/cleaning/basic.py`：

```python
@dataclass(frozen=True)
class ResolvedOperatorRun:
    """一次运行中已绑定 spec 和配置的逻辑算子。"""

    parsed_config: ParsedOperatorConfig
    spec: OperatorSpec
    merged_config: dict[str, object]
```

移除 `BackendAdapter`、`BackendOperatorRequest`、`BackendResult` 相关导入，新增：

```python
from image_gallery.operators.computers.base import (
    ComputeStage,
    ImageBatch,
    ImageBatchItem,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)
```

- [ ] **Step 4：替换 `_resolve_operator_configs()`**

```python
def _resolve_operator_configs(
    self,
    parsed_configs: list[ParsedOperatorConfig],
) -> list[ResolvedOperatorRun]:
    """解析算子配置，绑定 OperatorSpec 和合并后配置。"""
    resolved: list[ResolvedOperatorRun] = []
    for parsed_config in parsed_configs:
        spec = self._registry.get_operator(parsed_config.operator_name)
        merged = merge_default_config(parsed_config, spec.default_config)
        resolved.append(
            ResolvedOperatorRun(
                parsed_config=merged,
                spec=spec,
                merged_config=merged.config,
            )
        )
    return resolved
```

- [ ] **Step 5：新增参数需求和 computer 执行 helper**

```python
def _required_parameters(self, runs: list[ResolvedOperatorRun]) -> set[str]:
    """收集本次运行需要的全部参数字段。"""
    return {parameter for run in runs for parameter in run.spec.required_parameters}
```

```python
def _run_parameter_computers(self, runs: list[ResolvedOperatorRun]) -> dict[str, str]:
    """按 compute stage 执行参数计算单元并更新 parameter_table。"""
    required_parameters = self._required_parameters(runs)
    computers = self._registry.find_computers_for_parameters(required_parameters)
    artifact_paths: dict[str, str] = {}

    image_batch: ImageBatch | None = None
    if any(computer.stage == ComputeStage.IMAGE_BATCH for computer in computers):
        _, tables, _ = self._require_run(allow_missing_state=True)
        image_batch = self._build_image_batch(tables.parameter_table)

    for stage in (ComputeStage.IMAGE_BATCH, ComputeStage.TABLE_DERIVED, ComputeStage.DATASET_GLOBAL):
        for computer in [item for item in computers if item.stage == stage]:
            result = self._run_parameter_computer(computer, required_parameters, image_batch)
            _, tables, _ = self._require_run(allow_missing_state=True)
            self._tables = CleaningTables(
                parameter_table=update_parameter_columns(tables.parameter_table, result.parameter_updates),
                evaluation_table=tables.evaluation_table,
                operator_outputs=tables.operator_outputs,
            )
            artifact_paths.update(result.artifact_refs)
    return artifact_paths
```

```python
def _run_parameter_computer(
    self,
    computer: ParameterComputer,
    required_parameters: set[str],
    image_batch: ImageBatch | None,
) -> ParameterResult:
    """执行单个参数计算单元。"""
    context, tables, _ = self._require_run(allow_missing_state=True)
    requested_parameters = frozenset(required_parameters & set(computer.produced_parameters))
    return computer.compute(
        ParameterRequest(
            parameter_table=tables.parameter_table,
            requested_parameters=requested_parameters,
            config={},
            config_hash="default",
            artifacts_dir=context.paths.artifacts_dir,
            image_batch=image_batch if computer.stage == ComputeStage.IMAGE_BATCH else None,
        )
    )
```

- [ ] **Step 6：更新 `run()` 流程**

在 `run()` 中，将旧 backend loop 替换为：

```python
artifact_paths = self._run_parameter_computers(resolved_runs)
```

保留评估 loop：

```python
for resolved_run in resolved_runs:
    operator_states.append(self._evaluate_operator(resolved_run))
    _, tables, _ = self._require_run(allow_missing_state=True)
```

- [ ] **Step 7：更新 `rerun()` 为 evaluation-only 优先**

第一版不引入参数计算配置入口，因此 `rerun()` 对传入算子只重算 evaluation，不重算 parameter：

```python
for resolved_run in resolved_runs:
    operator_states.append(self._evaluate_operator(resolved_run))
```

不得调用 `_run_parameter_computers()`。后续当引入参数计算配置时，再通过 `parameter_manifest` 和参数配置 hash 判断是否需要重算参数。

删除不再引用的 `_group_by_backend()`、`_run_backend_group()`、`_runs_requiring_parameters()`。

- [ ] **Step 8：运行 BasicCleaner 单元测试**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_basic_cleaner.py -q
```

Expected：PASS，并验证：

```python
assert computer.calls == [({"demo_score"}, 2)]
```

- [ ] **Step 9：提交**

```bash
git add src/image_gallery/cleaning/basic.py tests/unit/cleaning/test_basic_cleaner.py
git commit -m "refactor: run cleaning through image batch computers"
```

---

## Task 7：内置 Decode 与 Dimension 集成验证

**Files:**
- Modify: `tests/integration/cleaning/test_basic_cleaner_builtin_run.py`
- Modify: `tests/integration/cleaning/test_basic_cleaner_export.py`
- Modify: `tests/integration/cleaning/test_basic_cleaner_rerun.py`

- [ ] **Step 1：用两个算子的垂直切片替换 builtin 集成测试**

`tests/integration/cleaning/test_basic_cleaner_builtin_run.py` 应构造三张图片：

1. 正常尺寸图片：最终 `keep`。
2. 小尺寸图片：最终 `review`。
3. 损坏图片：最终 `drop`。

核心配置：

```python
cleaner = BasicCleaner(
    [
        {"format.decode_check": {"action": "drop"}},
        {"size.dimension_check": {"min_width": 8, "min_height": 8, "action": "review"}},
    ]
)
```

核心断言：

```python
assert rows["ok"]["final_action"] == "keep"
assert rows["small"]["final_action"] == "review"
assert rows["bad"]["final_action"] == "drop"
assert cleaner.preview().total_count == 3
assert cleaner.preview().review_count == 1
assert cleaner.preview().dropped_count == 1
```

Run:

```bash
.venv/bin/python -m pytest tests/integration/cleaning/test_basic_cleaner_builtin_run.py -q
```

Expected：PASS。

- [ ] **Step 2：更新 export 集成测试**

`tests/integration/cleaning/test_basic_cleaner_export.py` 只使用：

```python
cleaner = BasicCleaner(
    [
        {"format.decode_check": {"action": "drop"}},
        {"size.dimension_check": {"min_width": 8, "min_height": 8, "action": "review"}},
    ]
)
```

预期：

```python
assert cleaner.export("full", str(tmp_path / "full.parquet")).count() == 3
assert cleaner.export("clean", str(tmp_path / "clean.parquet")).count() == 1
assert cleaner.export("review", str(tmp_path / "review.parquet")).count() == 1
assert cleaner.export("dropped", str(tmp_path / "dropped.parquet")).count() == 1
```

参数表至少应包含：

```text
image_id
image_uri
width
height
decode_error
decode_ok
```

- [ ] **Step 3：更新 rerun 集成测试，验证只重算 evaluation**

使用尺寸阈值变化验证重新评估：

```python
cleaner = BasicCleaner(
    [
        {"size.dimension_check": {"min_width": 8, "min_height": 8, "action": "review"}},
    ]
)
cleaner.run(dataset, output_dir=tmp_path / "cleaning")
assert cleaner.preview().review_count == 1

before_parameters = cleaner.export("parameters", str(tmp_path / "parameters_before.parquet")).to_frame()

cleaner.rerun(
    [
        {"size.dimension_check": {"min_width": 1, "min_height": 1, "action": "review"}},
    ]
)
assert cleaner.preview().review_count == 0

after_parameters = cleaner.export("parameters", str(tmp_path / "parameters_after.parquet")).to_frame()
assert before_parameters.equals(after_parameters)
```

Expected：`rerun()` 改变评估结果，但参数表不变。

- [ ] **Step 4：运行 cleaning 集成测试**

Run:

```bash
.venv/bin/python -m pytest tests/integration/cleaning -q
```

Expected：PASS。若存在旧算子配置，收敛到 `format.decode_check` 和 `size.dimension_check`。

- [ ] **Step 5：提交**

```bash
git add tests/integration/cleaning
git commit -m "test: validate v3 cleaning builtin slice"
```

---

## Task 8：最终清理旧模型引用

**Files:**
- Modify: `src/image_gallery/operators/__init__.py`
- Modify: `tests/unit/operators/`
- Modify: `docs/architecture/modules/清洗平台与算子库-v3.md`（仅当实现命名需要同步）

- [ ] **Step 1：搜索旧 backend 引用**

Run:

```bash
rg -n "BackendAdapter|BackendOperatorRequest|BackendResult|operators/backends|FastdupSimilarityBackend|fastdup_similarity_backend|duplicate.near_duplicate_check" src tests
```

Expected：`src` 和 active tests 中无匹配。

- [ ] **Step 2：运行 operator 测试**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators -q
```

Expected：PASS。

- [ ] **Step 3：提交**

如果有清理变更：

```bash
git add src tests docs
git commit -m "refactor: remove remaining backend model references"
```

如果无清理变更，跳过提交。

---

## Task 9：最终验证

**Files:**
- No planned edits.

- [ ] **Step 1：运行 v3 聚焦测试**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators tests/unit/cleaning tests/integration/cleaning -q
```

Expected：PASS。

- [ ] **Step 2：运行既有基础模块测试**

Run:

```bash
.venv/bin/python -m pytest tests/unit/storage tests/unit/dataset tests/unit/schemas tests/unit/importers -q
```

Expected：PASS。如果失败，先确认是否与本次清洗重构无关，不要随意改动非清洗模块。

- [ ] **Step 3：运行完整测试**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected：PASS。

- [ ] **Step 4：运行 lint 和类型检查**

Run:

```bash
.venv/bin/python -m ruff check src tests
.venv/bin/python -m mypy src/image_gallery
```

Expected：PASS。

---

## 验收标准

1. `BasicCleaner([{operator_name: config}, ...])` 公开 API 保持可用。
2. `create_default_registry().list_operators()` 只返回：
   - `format.decode_check`
   - `size.dimension_check`
3. `src/image_gallery/operators/backends/` 不存在。
4. `src` 和 active tests 中无 `BackendAdapter`、`BackendOperatorRequest`、`BackendResult` 引用。
5. `src` 和 active tests 中无 fastdup 默认执行引用。
6. `OperatorSpec` 使用 `required_parameters`，不再使用 `backend_name`。
7. `OperatorRegistry` 可以注册和解析 `ParameterComputer`。
8. `ImageBatch` 由 Cleaner 统一读取和解码图片后构建。
9. `ImageMetadataComputer` 只消费 `ImageBatch`，不调用 `Dataset.read_image*()`。
10. 单元测试证明两个逻辑算子共享一次 image batch 参数计算。
11. `rerun()` 只改评估配置时不改变 `parameter_table`。
12. 集成测试证明：正常图片 `keep`，小图 `review`，损坏图 `drop`。
13. 聚焦测试通过：

```bash
.venv/bin/python -m pytest tests/unit/operators tests/unit/cleaning tests/integration/cleaning -q
```

14. 合并前完整测试、ruff、mypy 通过：

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m mypy src/image_gallery
```

## 后续切片

本计划完成后，继续用独立计划推进：

1. `image_quality_computer` + `quality.blur_check`。
2. `image_quality_computer` + `quality.brightness_check` 和 `quality.contrast_check`。
3. `image_hash_computer` + `duplicate.exact_duplicate_check`。
4. `table_derived_computer` + `size.aspect_ratio_check`。
5. 基于 `parameter_manifest` 和参数配置 hash 支持参数计算配置变更后的局部重算。
6. 为未来近重复和聚类补充 relation/artifact manifest 支持。
