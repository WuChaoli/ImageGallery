# Semantic Duplicate Operator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `duplicate.semantic_duplicate_check` with ONNX DINOv2 image embeddings, Faiss-backed grouping, run-local artifacts, relation outputs, and configurable `drop` / `review` evaluation.

**Architecture:** Keep the current V3 split: `OperatorSpec` owns logical semantics and evaluation, while `ParameterComputer` owns image batch use, embedding artifacts, Faiss index artifacts, and relation tables. External providers are injected through registry construction, while operator configs stay JSON-serializable for config hashes and `state.json`.

**Tech Stack:** Python 3.10, pandas, numpy, Pillow, ONNX Runtime, Hugging Face Hub, Faiss CPU, pytest, ruff, mypy.

## Global Constraints

- Default provider: `onnx_dinov2_small`.
- Default model: `onnx-community/dinov2-small-ONNX`.
- Base model: `facebook/dinov2-small`.
- Embedding dimension: `384`.
- Embedding source: `cls_token`.
- Default index: `faiss_flat_ip`.
- Default threshold: `0.92`.
- Supported `keep`: only `"first"`.
- Supported `action`: `"drop"` and `"review"`.
- Store embeddings and Faiss index as cleaning run artifacts; do not write vectors into `parameter_table`.
- Do not add Milvus, Qdrant, Chroma, pgvector, or any vector database.
- Do not change `duplicate.exact_duplicate_check`, `duplicate.perceptual_duplicate_check`, export, or preview semantics.
- Provider objects must not appear in operator configs, config hashes, `operator_outputs.yaml`, or `state.json`.

---

## File Structure

- Modify: `pyproject.toml`
  - Add `semantic = ["onnxruntime>=1.18", "huggingface-hub>=0.24", "faiss-cpu>=1.8"]`.
- Create: `src/image_gallery/operators/semantic_provider.py`
  - Provider protocol, ONNX DINOv2 provider, injected provider loader.
- Create: `src/image_gallery/operators/computers/semantic.py`
  - `SemanticEmbeddingComputer`, `SemanticDuplicateGroupComputer`, artifact helpers.
- Modify: `src/image_gallery/operators/builtin.py`
  - Accept `semantic_providers`, register computers, register operator, add evaluator.
- Modify: `src/image_gallery/cleaning/basic.py`
  - Accept `semantic_providers` and pass them to `create_default_registry`.
- Test: `tests/unit/operators/test_semantic_provider.py`
- Test: `tests/unit/operators/test_semantic_computer.py`
- Modify: `tests/unit/operators/test_builtin_specs.py`
- Modify: `tests/unit/cleaning/test_planner.py`
- Test: `tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py`

---

### Task 1: Provider Boundary And Optional Dependencies

**Files:**
- Modify: `pyproject.toml`
- Create: `src/image_gallery/operators/semantic_provider.py`
- Test: `tests/unit/operators/test_semantic_provider.py`

**Interfaces:**
- Produces: `SemanticEmbeddingResult`
- Produces: `SemanticEmbeddingProvider.embed_images(images: list[Image.Image]) -> SemanticEmbeddingResult`
- Produces: `load_semantic_provider(config: dict[str, object], providers: dict[str, SemanticEmbeddingProvider] | None = None) -> SemanticEmbeddingProvider`

- [ ] **Step 1: Write failing provider tests**

Create `tests/unit/operators/test_semantic_provider.py`:

```python
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from image_gallery.operators.semantic_provider import (
    OnnxDinoV2SmallProvider,
    SemanticDependencyError,
    SemanticEmbeddingResult,
    SemanticEmbeddingProvider,
    load_semantic_provider,
)


class FakeProvider(SemanticEmbeddingProvider):
    provider_name = "fake"
    provider_version = "1"
    model_id = "fake-model"
    model_path = ""
    base_model = "fake-base"
    embedding_dimension = 3
    embedding_source = "unit"
    normalized = True

    def embed_images(self, images: list[Image.Image]) -> SemanticEmbeddingResult:
        return SemanticEmbeddingResult(
            embeddings=np.array([[1.0, 0.0, 0.0] for _ in images], dtype=np.float32),
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            model_id=self.model_id,
            model_path=self.model_path,
            base_model=self.base_model,
            embedding_dimension=self.embedding_dimension,
            embedding_source=self.embedding_source,
            normalized=self.normalized,
        )


def test_load_semantic_provider_accepts_named_injected_provider() -> None:
    provider = FakeProvider()

    loaded = load_semantic_provider({"provider": "fake"}, {"fake": provider})

    assert loaded is provider


def test_load_semantic_provider_rejects_unknown_provider_name() -> None:
    with pytest.raises(ValueError, match="unknown semantic provider"):
        load_semantic_provider({"provider": "missing"}, {})


def test_onnx_dinov2_provider_requires_existing_model_path(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.onnx"

    with pytest.raises(ValueError, match="model_path does not exist"):
        OnnxDinoV2SmallProvider(model_path=missing_path)


def test_default_provider_reports_missing_optional_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = __import__

    def fake_import(name: str, *args: object, **kwargs: object):
        if name == "onnxruntime":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(SemanticDependencyError, match="semantic optional dependencies"):
        load_semantic_provider({"provider": "onnx_dinov2_small"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/operators/test_semantic_provider.py -q`

Expected: fail with `ModuleNotFoundError: No module named 'image_gallery.operators.semantic_provider'`.

- [ ] **Step 3: Add semantic optional dependencies**

Modify `pyproject.toml`:

```toml
semantic = [
  "onnxruntime>=1.18",
  "huggingface-hub>=0.24",
  "faiss-cpu>=1.8"
]
```

- [ ] **Step 4: Implement provider module**

Create `src/image_gallery/operators/semantic_provider.py` with these public definitions:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray
from PIL import Image


class SemanticDependencyError(RuntimeError):
    """语义去重可选依赖缺失。"""


@dataclass(frozen=True)
class SemanticEmbeddingResult:
    """语义 embedding provider 的批量输出。"""

    embeddings: NDArray[np.float32]
    provider_name: str
    provider_version: str
    model_id: str
    model_path: str
    base_model: str
    embedding_dimension: int
    embedding_source: str
    normalized: bool


@runtime_checkable
class SemanticEmbeddingProvider(Protocol):
    """图片语义 embedding provider 协议。"""

    provider_name: str
    provider_version: str
    model_id: str
    model_path: str
    base_model: str
    embedding_dimension: int
    embedding_source: str
    normalized: bool

    def embed_images(self, images: list[Image.Image]) -> SemanticEmbeddingResult:
        """把图片批量转换为二维 embedding。"""


class OnnxDinoV2SmallProvider:
    """基于 ONNX Runtime 的 DINOv2-small 图片 embedding provider。"""

    provider_name = "onnx_dinov2_small"
    provider_version = "1"
    model_id = "onnx-community/dinov2-small-ONNX"
    base_model = "facebook/dinov2-small"
    embedding_dimension = 384
    embedding_source = "cls_token"
    normalized = True

    def __init__(self, model_path: str | Path | None = None) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise SemanticDependencyError(
                "semantic optional dependencies are required; install image-gallery[semantic]"
            ) from exc
        resolved_path = _resolve_model_path(model_path, self.model_id)
        self.model_path = str(resolved_path)
        self._session = ort.InferenceSession(str(resolved_path), providers=["CPUExecutionProvider"])
        self._input_name = self._session.get_inputs()[0].name

    def embed_images(self, images: list[Image.Image]) -> SemanticEmbeddingResult:
        """运行 DINOv2-small ONNX 模型并返回归一化 cls token embedding。"""
        if not images:
            embeddings = np.empty((0, self.embedding_dimension), dtype=np.float32)
        else:
            batch = np.stack([_preprocess_image(image) for image in images]).astype(np.float32)
            output = self._session.run(None, {self._input_name: batch})[0]
            embeddings = _l2_normalize(_extract_cls_embedding(output, self.embedding_dimension))
        return SemanticEmbeddingResult(
            embeddings=embeddings.astype(np.float32),
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            model_id=self.model_id,
            model_path=self.model_path,
            base_model=self.base_model,
            embedding_dimension=self.embedding_dimension,
            embedding_source=self.embedding_source,
            normalized=self.normalized,
        )


def load_semantic_provider(
    config: dict[str, object],
    providers: dict[str, SemanticEmbeddingProvider] | None = None,
) -> SemanticEmbeddingProvider:
    """按配置加载语义 embedding provider。"""
    provider_name = str(config.get("provider", "onnx_dinov2_small"))
    if providers is not None and provider_name in providers:
        return providers[provider_name]
    if provider_name != "onnx_dinov2_small":
        raise ValueError(f"unknown semantic provider: {provider_name}")
    model_path = config.get("model_path")
    return OnnxDinoV2SmallProvider(None if model_path is None else str(model_path))


def _resolve_model_path(model_path: str | Path | None, model_id: str) -> Path:
    """解析本地模型路径，未提供时从 Hugging Face Hub 下载。"""
    if model_path is not None:
        path = Path(model_path)
        if not path.exists():
            raise ValueError(f"model_path does not exist: {path}")
        return path
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise SemanticDependencyError(
            "semantic optional dependencies are required; install image-gallery[semantic]"
        ) from exc
    return Path(hf_hub_download(repo_id=model_id, filename="onnx/model.onnx"))


def _preprocess_image(image: Image.Image) -> NDArray[np.float32]:
    """按 DINOv2 常用 ImageNet 归一化预处理图片。"""
    resized = image.convert("RGB").resize((224, 224), Image.Resampling.BICUBIC)
    array = np.asarray(resized, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    return np.transpose((array - mean) / std, (2, 0, 1))


def _extract_cls_embedding(output: NDArray[np.float32], dimension: int) -> NDArray[np.float32]:
    """从 ONNX 输出中提取 cls token embedding。"""
    array = np.asarray(output, dtype=np.float32)
    embeddings = array[:, 0, :] if array.ndim == 3 else array
    if embeddings.ndim != 2 or embeddings.shape[1] != dimension:
        raise ValueError(f"expected embedding dimension {dimension}, got shape {embeddings.shape}")
    return embeddings


def _l2_normalize(embeddings: NDArray[np.float32]) -> NDArray[np.float32]:
    """对 embedding 做 L2 归一化。"""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    if np.any(norms <= 0) or not np.isfinite(norms).all():
        raise ValueError("embedding contains zero or non-finite norm")
    return embeddings / norms
```

- [ ] **Step 5: Run provider tests**

Run: `.venv/bin/python -m pytest tests/unit/operators/test_semantic_provider.py -q`

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/image_gallery/operators/semantic_provider.py tests/unit/operators/test_semantic_provider.py
git commit -m "feat: add semantic embedding provider boundary"
```

---

### Task 2: Embedding Artifact Computer

**Files:**
- Create: `src/image_gallery/operators/computers/semantic.py`
- Test: `tests/unit/operators/test_semantic_computer.py`

**Interfaces:**
- Produces: `SemanticEmbeddingComputer(providers: dict[str, SemanticEmbeddingProvider] | None = None)`
- Produces parameter: `semantic_embedding_ref`
- Produces artifact ref: `semantic_embeddings`

- [ ] **Step 1: Write failing embedding artifact tests**

Create `tests/unit/operators/test_semantic_computer.py` with:

```python
from pathlib import Path

import json
import numpy as np
import pandas as pd
import pytest
from PIL import Image

from image_gallery.operators.computers.base import ImageBatch, ImageBatchItem, ParameterRequest
from image_gallery.operators.computers.semantic import SemanticEmbeddingComputer
from image_gallery.operators.semantic_provider import SemanticEmbeddingResult, SemanticEmbeddingProvider


class FakeSemanticProvider(SemanticEmbeddingProvider):
    provider_name = "fake_provider"
    provider_version = "1"
    model_id = "fake-model"
    model_path = "/tmp/fake.onnx"
    base_model = "fake-base"
    embedding_dimension = 3
    embedding_source = "unit"
    normalized = True

    def __init__(self, embeddings: np.ndarray) -> None:
        self._embeddings = embeddings.astype(np.float32)

    def embed_images(self, images: list[Image.Image]) -> SemanticEmbeddingResult:
        return SemanticEmbeddingResult(
            embeddings=self._embeddings[: len(images)],
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            model_id=self.model_id,
            model_path=self.model_path,
            base_model=self.base_model,
            embedding_dimension=self.embedding_dimension,
            embedding_source=self.embedding_source,
            normalized=self.normalized,
        )


def _request(tmp_path: Path, provider_name: str = "fake") -> ParameterRequest:
    image = Image.new("RGB", (8, 8), color=(100, 120, 140))
    return ParameterRequest(
        parameter_table=pd.DataFrame({"image_id": ["a", "b"], "image_uri": ["a.png", "b.png"]}),
        requested_parameters=frozenset({"semantic_embedding_ref"}),
        config={"provider": provider_name},
        config_hash="cfg",
        artifacts_dir=tmp_path / "artifacts",
        image_batch=ImageBatch(
            items=[
                ImageBatchItem("a", "a.png", {}, b"a", image, None),
                ImageBatchItem("b", "b.png", {}, b"b", None, "decode failed"),
            ]
        ),
    )


def test_semantic_embedding_computer_writes_artifact_and_refs(tmp_path: Path) -> None:
    provider = FakeSemanticProvider(np.array([[1.0, 0.0, 0.0]], dtype=np.float32))

    result = SemanticEmbeddingComputer({"fake": provider}).compute(_request(tmp_path))

    artifact_dir = tmp_path / "artifacts" / "semantic_embeddings"
    assert np.load(artifact_dir / "embeddings.npy").tolist() == [[1.0, 0.0, 0.0]]
    assert pd.read_parquet(artifact_dir / "image_ids.parquet")["image_id"].tolist() == ["a"]
    assert json.loads((artifact_dir / "manifest.json").read_text())["embedding_dimension"] == 3
    assert result.parameter_updates.to_dict(orient="records") == [
        {"image_id": "a", "semantic_embedding_ref": str(artifact_dir)},
        {"image_id": "b", "semantic_embedding_ref": ""},
    ]
    assert result.artifact_refs == {"semantic_embeddings": str(artifact_dir)}


def test_semantic_embedding_computer_rejects_non_finite_vectors(tmp_path: Path) -> None:
    provider = FakeSemanticProvider(np.array([[float("nan"), 0.0, 0.0]], dtype=np.float32))

    with pytest.raises(ValueError, match="non-finite"):
        SemanticEmbeddingComputer({"fake": provider}).compute(_request(tmp_path))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/operators/test_semantic_computer.py -q`

Expected: fail with missing `image_gallery.operators.computers.semantic`.

- [ ] **Step 3: Implement `SemanticEmbeddingComputer`**

Create `src/image_gallery/operators/computers/semantic.py` with `SemanticEmbeddingComputer`, `_validate_embeddings`, and `_write_embedding_manifest`. Required behavior:

```python
class SemanticEmbeddingComputer(ParameterComputer):
    """生成语义 embedding artifact，并在参数表中写入引用。"""

    name = "semantic_embedding_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"semantic_embedding_ref"})

    def __init__(self, providers: dict[str, SemanticEmbeddingProvider] | None = None) -> None:
        self._providers = providers or {}
```

`compute()` must:

- require `request.image_batch`;
- select valid decoded images only;
- call `load_semantic_provider(request.config, self._providers)`;
- write `artifacts/semantic_embeddings/embeddings.npy`;
- write `artifacts/semantic_embeddings/image_ids.parquet`;
- write `artifacts/semantic_embeddings/manifest.json`;
- return `semantic_embedding_ref` as the artifact directory for valid rows and `""` for decode failures;
- return `artifact_refs={"semantic_embeddings": str(artifact_dir)}`.

- [ ] **Step 4: Run embedding tests**

Run: `.venv/bin/python -m pytest tests/unit/operators/test_semantic_computer.py -q`

Expected: the two embedding tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/image_gallery/operators/computers/semantic.py tests/unit/operators/test_semantic_computer.py
git commit -m "feat: write semantic embedding artifacts"
```

---

### Task 3: Semantic Grouping And Faiss Artifact

**Files:**
- Modify: `src/image_gallery/operators/computers/semantic.py`
- Modify: `tests/unit/operators/test_semantic_computer.py`

**Interfaces:**
- Produces: `SemanticDuplicateGroupComputer`
- Produces parameters: `semantic_duplicate_group_id`, `semantic_duplicate_count`, `semantic_duplicate_score`, `semantic_duplicate_nearest_image_id`
- Produces relation: `semantic_duplicate_pairs`
- Produces artifact ref: `semantic_index`

- [ ] **Step 1: Add failing grouping tests**

Append tests that write an embedding artifact with vectors `keeper=[1,0,0]`, `near=[0.99,0.01,0]`, `far=[0,1,0]`, then assert threshold `0.9` groups keeper+near, writes `relations/semantic_duplicate_pairs`, and writes `artifacts/semantic_index/faiss.index`.

Use this core assertion:

```python
result = SemanticDuplicateGroupComputer().compute(request)
rows = result.parameter_updates.set_index("image_id")
assert rows.loc["keeper", "semantic_duplicate_count"] == 2
assert rows.loc["near", "semantic_duplicate_nearest_image_id"] == "keeper"
assert rows.loc["far", "semantic_duplicate_group_id"] == ""
assert result.relation_updates["semantic_duplicate_pairs"]["relation_type"].tolist() == ["semantic_duplicate"]
assert Path(result.artifact_refs["semantic_index"]).exists()
```

Also add a no-valid-ref test:

```python
result = SemanticDuplicateGroupComputer().compute(request_with_empty_semantic_embedding_ref)
assert result.parameter_updates["semantic_duplicate_group_id"].tolist() == [""]
assert result.relation_updates["semantic_duplicate_pairs"].empty
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/operators/test_semantic_computer.py -q`

Expected: fail with missing `SemanticDuplicateGroupComputer`.

- [ ] **Step 3: Implement `SemanticDuplicateGroupComputer`**

In `src/image_gallery/operators/computers/semantic.py`, implement:

```python
class SemanticDuplicateGroupComputer(ParameterComputer):
    """基于语义 embedding 和 Faiss index 生成语义重复组。"""

    name = "semantic_duplicate_group_computer"
    execution_mode = ExecutionMode.DATASET_AGGREGATE
    produced_parameters = frozenset(
        {
            "semantic_duplicate_group_id",
            "semantic_duplicate_count",
            "semantic_duplicate_score",
            "semantic_duplicate_nearest_image_id",
        }
    )
    required_parameters = frozenset({"semantic_embedding_ref"})
```

`compute()` must:

- read the first non-empty `semantic_embedding_ref`;
- return empty keep-all rows if no ref exists;
- read `embeddings.npy`, `image_ids.parquet`, and `manifest.json`;
- require `index == "faiss_flat_ip"`;
- require `faiss` import, otherwise raise `RuntimeError("faiss-cpu is required...")`;
- write `artifacts/semantic_index/faiss.index` with `faiss.IndexFlatIP`;
- write `artifacts/semantic_index/manifest.json`;
- scan in `parameter_table` order and group each image against existing keepers by dot product;
- write relation rows with `relation_type="semantic_duplicate"` and `artifact_ref` pointing to `faiss.index`;
- write parameter manifest for all four semantic duplicate parameters.

- [ ] **Step 4: Run grouping tests**

Run: `.venv/bin/python -m pytest tests/unit/operators/test_semantic_computer.py -q`

Expected: pass. If `faiss-cpu` is not installed, run `.venv/bin/python -m pip install -e ".[semantic]"`.

- [ ] **Step 5: Commit**

```bash
git add src/image_gallery/operators/computers/semantic.py tests/unit/operators/test_semantic_computer.py
git commit -m "feat: group semantic duplicate embeddings"
```

---

### Task 4: Registry, BasicCleaner Injection, And Evaluator

**Files:**
- Modify: `src/image_gallery/operators/builtin.py`
- Modify: `src/image_gallery/cleaning/basic.py`
- Modify: `src/image_gallery/operators/computers/__init__.py`
- Modify: `tests/unit/operators/test_builtin_specs.py`
- Modify: `tests/unit/cleaning/test_planner.py`

**Interfaces:**
- Produces: `create_default_registry(semantic_providers: dict[str, SemanticEmbeddingProvider] | None = None)`
- Produces: `BasicCleaner(..., semantic_providers: dict[str, SemanticEmbeddingProvider] | None = None)`
- Produces: `evaluate_semantic_duplicate_check(...)`

- [ ] **Step 1: Add failing registry and planner tests**

In `tests/unit/operators/test_builtin_specs.py`, add:

```python
def test_semantic_duplicate_spec_declares_required_parameters() -> None:
    registry = create_default_registry()
    spec = registry.get_operator("duplicate.semantic_duplicate_check")
    assert spec.required_parameters == [
        "semantic_duplicate_group_id",
        "semantic_duplicate_count",
        "semantic_duplicate_score",
        "semantic_duplicate_nearest_image_id",
    ]
    assert spec.default_config["provider"] == "onnx_dinov2_small"
    assert spec.default_config["model_id"] == "onnx-community/dinov2-small-ONNX"
```

Add evaluator test:

```python
def test_semantic_duplicate_evaluator_supports_drop_and_review() -> None:
    registry = create_default_registry()
    frame = pd.DataFrame(
        {
            "image_id": ["first", "second", "unique"],
            "semantic_duplicate_group_id": ["semantic-first", "semantic-first", ""],
            "semantic_duplicate_count": [2, 2, 1],
            "semantic_duplicate_score": [1.0, 0.95, pd.NA],
            "semantic_duplicate_nearest_image_id": ["", "first", ""],
        }
    )
    drop_result = registry.get_operator("duplicate.semantic_duplicate_check").evaluate(
        frame, {"keep": "first", "action": "drop"}
    )
    review_result = registry.get_operator("duplicate.semantic_duplicate_check").evaluate(
        frame, {"keep": "first", "action": "review"}
    )
    assert drop_result["semantic_duplicate_action"].tolist() == ["keep", "drop", "keep"]
    assert review_result["semantic_duplicate_action"].tolist() == ["keep", "review", "keep"]
```

In `tests/unit/cleaning/test_planner.py`, add:

```python
def test_builtin_planner_expands_semantic_duplicate_dependencies() -> None:
    parsed = parse_operator_configs([{"duplicate.semantic_duplicate_check": {"provider": "fake"}}])
    plan = CleaningRunPlanner(create_default_registry()).compile(parsed)
    assert [step.computer_name for step in plan.parameter_plan.steps] == [
        "semantic_embedding_computer",
        "semantic_duplicate_group_computer",
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/operators/test_builtin_specs.py::test_semantic_duplicate_spec_declares_required_parameters tests/unit/cleaning/test_planner.py::test_builtin_planner_expands_semantic_duplicate_dependencies -q`

Expected: fail with `unknown operator: duplicate.semantic_duplicate_check`.

- [ ] **Step 3: Register computers and operator**

Modify `create_default_registry`:

```python
def create_default_registry(semantic_providers: dict[str, SemanticEmbeddingProvider] | None = None) -> OperatorRegistry:
    """创建包含第一版 v3 基础逻辑算子和参数计算单元的注册表。"""
```

Register:

```python
registry.register_parameter_computer(SemanticEmbeddingComputer(semantic_providers))
registry.register_parameter_computer(SemanticDuplicateGroupComputer())
```

Add `OperatorSpec(name="duplicate.semantic_duplicate_check", ...)` with the columns and defaults from the spec.

- [ ] **Step 4: Add evaluator**

Add:

```python
def evaluate_semantic_duplicate_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据语义重复组生成去重结果。"""
    keep = str(config.get("keep", "first"))
    if keep != "first":
        raise ValueError("duplicate.semantic_duplicate_check only supports keep='first'")
    action = str(config.get("action", "drop"))
    if action not in {"drop", "review"}:
        raise ValueError("duplicate.semantic_duplicate_check only supports action='drop' or action='review'")
    groups = parameter_table["semantic_duplicate_group_id"].fillna("").astype(str)
    counts = pd.to_numeric(parameter_table["semantic_duplicate_count"], errors="coerce").fillna(1).astype(int)
    scores = pd.to_numeric(parameter_table["semantic_duplicate_score"], errors="coerce")
    nearest_ids = parameter_table["semantic_duplicate_nearest_image_id"].fillna("").astype(str)
    seen_groups: set[str] = set()
    actions: list[str] = []
    reasons: list[str] = []
    for group_id, count, score, nearest_id in zip(groups.tolist(), counts.tolist(), scores.tolist(), nearest_ids.tolist(), strict=True):
        if not group_id or count <= 1:
            actions.append("keep")
            reasons.append("")
        elif group_id not in seen_groups:
            seen_groups.add(group_id)
            actions.append("keep")
            reasons.append("")
        else:
            actions.append(action)
            reasons.append(f"semantic duplicate in group {group_id} score {float(score):.4f} nearest {nearest_id}")
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "semantic_duplicate_group_id": groups,
            "semantic_duplicate_count": counts,
            "semantic_duplicate_score": scores,
            "semantic_duplicate_nearest_image_id": nearest_ids,
            "semantic_duplicate_action": actions,
            "semantic_duplicate_reason": reasons,
        }
    )
```

- [ ] **Step 5: Add BasicCleaner injection**

Modify `BasicCleaner.__init__`:

```python
def __init__(
    self,
    operator_configs: OperatorConfigInput,
    output_dir: str | Path | None = None,
    registry: OperatorRegistry | None = None,
    semantic_providers: dict[str, SemanticEmbeddingProvider] | None = None,
) -> None:
    self._operator_configs = parse_operator_configs(operator_configs)
    self._registry = registry if registry is not None else create_default_registry(semantic_providers)
```

- [ ] **Step 6: Run registry/planner tests**

Run: `.venv/bin/python -m pytest tests/unit/operators/test_builtin_specs.py tests/unit/cleaning/test_planner.py -q`

Expected: pass after updating the expected default operator list to include `"duplicate.semantic_duplicate_check"`.

- [ ] **Step 7: Commit**

```bash
git add src/image_gallery/operators/builtin.py src/image_gallery/cleaning/basic.py src/image_gallery/operators/computers/__init__.py tests/unit/operators/test_builtin_specs.py tests/unit/cleaning/test_planner.py
git commit -m "feat: register semantic duplicate operator"
```

---

### Task 5: BasicCleaner Integration

**Files:**
- Create: `tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py`

**Interfaces:**
- Consumes: `BasicCleaner(semantic_providers={...})`
- Consumes serializable operator config: `{"provider": "deterministic"}`

- [ ] **Step 1: Write integration test**

Create `tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py` with deterministic provider returning normalized vectors `[1,0,0]`, `[0.99,0.01,0]`, `[0,1,0]`.

Core test body:

```python
cleaner = BasicCleaner(
    [
        {
            "duplicate.semantic_duplicate_check": {
                "threshold": 0.9,
                "action": "drop",
                "provider": "deterministic",
            }
        }
    ],
    semantic_providers={"deterministic": DeterministicSemanticProvider()},
)
cleaner.run(dataset, output_dir=tmp_path / "cleaning")
full = cleaner.export("full", str(tmp_path / "full.parquet")).to_frame().set_index("image_id")
assert full.loc["first", "semantic_duplicate_action"] == "keep"
assert full.loc["near", "semantic_duplicate_action"] == "drop"
assert full.loc["far", "semantic_duplicate_action"] == "keep"
run_dir = next((tmp_path / "cleaning").iterdir())
assert (run_dir / "artifacts" / "semantic_embeddings" / "embeddings.npy").exists()
assert (run_dir / "artifacts" / "semantic_index" / "faiss.index").exists()
assert (run_dir / "relations" / "semantic_duplicate_pairs.parquet").exists()
```

Also assert `state.json` can be loaded with `json.loads` and does not contain `DeterministicSemanticProvider`.

- [ ] **Step 2: Run integration test**

Run: `.venv/bin/python -m pytest tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py -q`

Expected: pass. If `faiss-cpu` is missing, run `.venv/bin/python -m pip install -e ".[semantic]"`.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py
git commit -m "test: validate semantic duplicate cleaning run"
```

---

### Task 6: Final Verification

**Files:**
- Modify only if tests require it: `notebooks/_helpers/cleaning_configs.py`

**Interfaces:**
- Produces final verified implementation.

- [ ] **Step 1: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators tests/unit/cleaning tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py -q
```

Expected: pass.

- [ ] **Step 2: Run lint and type checks**

Run:

```bash
.venv/bin/python -m ruff check src tests
.venv/bin/python -m mypy src/image_gallery
```

Expected: pass.

- [ ] **Step 3: Optional notebook helper**

If adding a semantic helper is useful, only add a serializable config helper:

```python
def get_semantic_duplicate_operator_config(provider: str = "onnx_dinov2_small") -> list[dict[str, dict[str, object]]]:
    """返回语义去重算子的测试配置。"""
    return [{"duplicate.semantic_duplicate_check": {"threshold": 0.9, "action": "drop", "provider": provider}}]
```

Do not add semantic duplicate to `get_cleaning_v3_first_batch_operator_configs()` because semantic dependencies are optional.

- [ ] **Step 4: Commit validation fixes if any**

```bash
git add notebooks/_helpers/cleaning_configs.py src tests
git commit -m "chore: finalize semantic duplicate validation"
```

Skip this commit if no files changed.

---

## Self-Review

**Spec coverage:** Covers semantic operator, ONNX DINOv2 default provider, external provider injection, Faiss artifact, embedding artifact, relation table, `drop` / `review`, no vector database, and no pHash/export/preview behavior changes.

**Placeholder scan:** No task uses placeholder language. Each task has exact files, commands, expected outcomes, and commit boundaries.

**Type consistency:** Provider injection is consistently registry-level via `semantic_providers`; operator configs remain serializable via `provider` string.
