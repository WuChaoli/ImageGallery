# pHash Duplicate Operator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `duplicate.perceptual_duplicate_check`, a pHash-based duplicate operator that drops non-first images whose Hamming distance is within a configured threshold.

**Architecture:** Add one `PER_IMAGE` computer for `phash` and one `DATASET_AGGREGATE` computer for perceptual duplicate grouping. Register a new logical operator in the built-in registry and keep exact duplicate behavior unchanged. Reuse the existing planner, scheduler, relation table writer, evaluator, and BasicCleaner APIs.

**Tech Stack:** Python 3.10, pandas, numpy, Pillow, pytest, ruff, mypy, ImageGallery `BasicCleaner`, `OperatorRegistry`, `ParameterComputer`.

## Global Constraints

- User-facing operator name is `duplicate.perceptual_duplicate_check`.
- Do not implement or register `duplicate.near_duplicate_check`.
- Do not add new runtime dependencies; use existing `Pillow + numpy`.
- Default config is exactly `{"max_distance": 10, "keep": "first", "action": "drop"}`.
- First version only outputs `drop` or `keep`; do not add `review`.
- First version only supports `keep="first"` and `action="drop"`.
- Keep `duplicate.exact_duplicate_check` behavior unchanged.
- Use `.venv/bin/python` for all Python commands.

---

## File Structure

Modify:

- `src/image_gallery/operators/computers/hash.py`
  - Add `ImagePerceptualHashComputer`.
  - Add private helpers `_compute_phash()`, `_dct_matrix()`, and `_bits_to_hex()`.
  - Keep `ImageHashComputer` unchanged except for shared imports.

- `src/image_gallery/operators/computers/duplicate.py`
  - Add `PerceptualDuplicateGroupComputer`.
  - Add private helpers `_hamming_distance()`, `_build_perceptual_groups()`, and `_build_perceptual_duplicate_pairs()`.
  - Keep `DuplicateGroupComputer` unchanged.

- `src/image_gallery/operators/builtin.py`
  - Register `ImagePerceptualHashComputer` and `PerceptualDuplicateGroupComputer`.
  - Add `duplicate.perceptual_duplicate_check` spec.
  - Add `evaluate_perceptual_duplicate_check()`.

- `notebooks/_helpers/cleaning_configs.py`
  - Add `{"duplicate.perceptual_duplicate_check": {}}` to the shared first-batch notebook/integration config.

Tests:

- `tests/unit/operators/test_hash_computer.py`
  - Add pHash computer unit tests.

- `tests/unit/operators/test_duplicate_computer.py`
  - Add perceptual duplicate group tests.

- `tests/unit/operators/test_builtin_specs.py`
  - Add registry and evaluator tests.

- `tests/unit/cleaning/test_planner.py`
  - Add built-in planner test for perceptual duplicate dependency expansion.

- `tests/integration/cleaning/test_basic_cleaner_builtin_run.py`
  - Add perceptual duplicate operator to the local integration case and assert output columns/relation file.

---

### Task 1: Add pHash Parameter Computer

**Files:**
- Modify: `src/image_gallery/operators/computers/hash.py`
- Modify: `tests/unit/operators/test_hash_computer.py`

**Interfaces:**
- Consumes: `ImageBatchItem.image: PIL.Image.Image | None`
- Produces:
  - `ImagePerceptualHashComputer.name = "image_perceptual_hash_computer"`
  - `ImagePerceptualHashComputer.execution_mode = ExecutionMode.PER_IMAGE`
  - `ImagePerceptualHashComputer.produced_parameters = frozenset({"phash"})`
  - `phash` values as 16-character lowercase hex strings, or `""` for unreadable images.

- [ ] **Step 1: Write failing pHash computer tests**

Append to `tests/unit/operators/test_hash_computer.py`:

```python
import re

from image_gallery.operators.computers.hash import ImagePerceptualHashComputer


def test_perceptual_hash_computer_returns_stable_16_char_hex(tmp_path) -> None:
    image = Image.new("RGB", (32, 32), color=(120, 130, 140))
    batch = ImageBatch(
        items=[
            ImageBatchItem("img-1", "/tmp/img-1.png", {"image_id": "img-1"}, b"bytes-1", image, None),
            ImageBatchItem("img-2", "/tmp/img-2.png", {"image_id": "img-2"}, b"bytes-2", image.copy(), None),
        ]
    )

    result = ImagePerceptualHashComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["img-1", "img-2"]}),
            requested_parameters=frozenset({"phash"}),
            config={},
            config_hash="default",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    values = result.parameter_updates["phash"].tolist()
    assert values[0] == values[1]
    assert re.fullmatch(r"[0-9a-f]{16}", values[0])
    assert result.parameter_manifest["phash"]["computer"] == "image_perceptual_hash_computer"
    assert result.parameter_manifest["phash"]["execution_mode"] == "per_image"


def test_perceptual_hash_computer_returns_empty_hash_for_unreadable_image(tmp_path) -> None:
    batch = ImageBatch(
        items=[
            ImageBatchItem("bad", "/tmp/bad.jpg", {"image_id": "bad"}, None, None, "cannot decode"),
        ]
    )

    result = ImagePerceptualHashComputer().compute(
        ParameterRequest(
            parameter_table=pd.DataFrame({"image_id": ["bad"]}),
            requested_parameters=frozenset({"phash"}),
            config={},
            config_hash="default",
            artifacts_dir=tmp_path,
            image_batch=batch,
        )
    )

    assert result.parameter_updates.to_dict(orient="records") == [{"image_id": "bad", "phash": ""}]
```

- [ ] **Step 2: Run the focused hash tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_hash_computer.py -q
```

Expected: FAIL with `ImportError` or `NameError` for `ImagePerceptualHashComputer`.

- [ ] **Step 3: Implement `ImagePerceptualHashComputer`**

Modify `src/image_gallery/operators/computers/hash.py` to include these imports:

```python
from functools import lru_cache

import numpy as np
from numpy.typing import NDArray
from PIL import Image
```

Add the class after `ImageHashComputer`:

```python
class ImagePerceptualHashComputer(ParameterComputer):
    """基于解码图片生产视觉感知哈希。"""

    name = "image_perceptual_hash_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"phash"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """生产 16 位十六进制 pHash。"""
        if request.image_batch is None:
            raise ValueError("ImagePerceptualHashComputer requires image_batch")

        rows: list[dict[str, object]] = []
        for item in request.image_batch.items:
            phash = _compute_phash(item.image) if item.image is not None and item.error is None else ""
            rows.append({"image_id": item.image_id, "phash": phash})

        return ParameterResult(
            parameter_updates=pd.DataFrame(rows),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={
                "phash": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                }
            },
        )
```

Add helpers at the bottom of `hash.py`:

```python
def _compute_phash(image: Image.Image) -> str:
    """计算 64 位 DCT pHash，并编码为 16 位十六进制。"""
    grayscale = image.convert("L").resize((32, 32), Image.Resampling.LANCZOS)
    pixels = np.asarray(grayscale, dtype=np.float64)
    dct = _dct_matrix(32) @ pixels @ _dct_matrix(32).T
    low_freq = dct[:8, :8].copy()
    values = low_freq.flatten()
    median = float(np.median(values[1:]))
    bits = values >= median
    return _bits_to_hex(bits)


@lru_cache(maxsize=4)
def _dct_matrix(size: int) -> NDArray[np.float64]:
    """生成 DCT-II 正交变换矩阵。"""
    matrix = np.zeros((size, size), dtype=np.float64)
    factor = np.pi / (2.0 * size)
    scale0 = np.sqrt(1.0 / size)
    scale = np.sqrt(2.0 / size)
    for row in range(size):
        alpha = scale0 if row == 0 else scale
        for column in range(size):
            matrix[row, column] = alpha * np.cos((2 * column + 1) * row * factor)
    return matrix


def _bits_to_hex(bits: NDArray[np.bool_]) -> str:
    """把 64 个布尔位编码为 16 位十六进制字符串。"""
    value = 0
    for bit in bits.tolist():
        value = (value << 1) | int(bool(bit))
    return f"{value:016x}"
```

- [ ] **Step 4: Run the focused hash tests and verify pass**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_hash_computer.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/image_gallery/operators/computers/hash.py tests/unit/operators/test_hash_computer.py
git commit -m "feat: add perceptual hash computer"
```

---

### Task 2: Add Perceptual Duplicate Group Computer

**Files:**
- Modify: `src/image_gallery/operators/computers/duplicate.py`
- Modify: `tests/unit/operators/test_duplicate_computer.py`

**Interfaces:**
- Consumes:
  - `parameter_table["image_id"]`
  - `parameter_table["phash"]`
  - `ParameterRequest.config["max_distance"]`, default `10`
- Produces:
  - `PerceptualDuplicateGroupComputer.name = "perceptual_duplicate_group_computer"`
  - `produced_parameters = frozenset({"perceptual_duplicate_group_id", "perceptual_duplicate_count", "perceptual_duplicate_distance"})`
  - `required_parameters = frozenset({"phash"})`
  - relation update key `perceptual_duplicate_pairs`

- [ ] **Step 1: Write failing duplicate group tests**

Append to `tests/unit/operators/test_duplicate_computer.py`:

```python
from image_gallery.operators.computers.duplicate import PerceptualDuplicateGroupComputer


def test_perceptual_duplicate_group_computer_groups_hashes_within_distance(tmp_path) -> None:
    frame = pd.DataFrame(
        {
            "image_id": ["keeper", "near", "far"],
            "phash": ["0000000000000000", "0000000000000001", "ffffffffffffffff"],
        }
    )

    result = PerceptualDuplicateGroupComputer().compute(
        ParameterRequest(
            parameter_table=frame,
            requested_parameters=frozenset(
                {
                    "perceptual_duplicate_group_id",
                    "perceptual_duplicate_count",
                    "perceptual_duplicate_distance",
                }
            ),
            config={"max_distance": 10},
            config_hash="default",
            artifacts_dir=tmp_path,
        )
    )

    assert result.parameter_updates.to_dict(orient="records") == [
        {
            "image_id": "keeper",
            "perceptual_duplicate_group_id": "perceptual-0000000000000000",
            "perceptual_duplicate_count": 2,
            "perceptual_duplicate_distance": 0,
        },
        {
            "image_id": "near",
            "perceptual_duplicate_group_id": "perceptual-0000000000000000",
            "perceptual_duplicate_count": 2,
            "perceptual_duplicate_distance": 1,
        },
        {
            "image_id": "far",
            "perceptual_duplicate_group_id": "",
            "perceptual_duplicate_count": 1,
            "perceptual_duplicate_distance": pd.NA,
        },
    ]
    pairs = result.relation_updates["perceptual_duplicate_pairs"]
    assert pairs[["relation_type", "source_image_id", "target_image_id", "score", "group_id"]].to_dict(
        orient="records"
    ) == [
        {
            "relation_type": "perceptual_duplicate",
            "source_image_id": "keeper",
            "target_image_id": "near",
            "score": 1.0 - 1.0 / 64.0,
            "group_id": "perceptual-0000000000000000",
        }
    ]


def test_perceptual_duplicate_group_computer_ignores_empty_hashes(tmp_path) -> None:
    frame = pd.DataFrame({"image_id": ["bad"], "phash": [""]})

    result = PerceptualDuplicateGroupComputer().compute(
        ParameterRequest(
            parameter_table=frame,
            requested_parameters=frozenset({"perceptual_duplicate_group_id"}),
            config={},
            config_hash="default",
            artifacts_dir=tmp_path,
        )
    )

    assert result.parameter_updates.to_dict(orient="records") == [
        {
            "image_id": "bad",
            "perceptual_duplicate_group_id": "",
            "perceptual_duplicate_count": 1,
            "perceptual_duplicate_distance": pd.NA,
        }
    ]
```

- [ ] **Step 2: Run duplicate computer tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_duplicate_computer.py -q
```

Expected: FAIL with `ImportError` or `NameError` for `PerceptualDuplicateGroupComputer`.

- [ ] **Step 3: Implement grouping computer and helpers**

Append to `src/image_gallery/operators/computers/duplicate.py` after `DuplicateGroupComputer`:

```python
class PerceptualDuplicateGroupComputer(ParameterComputer):
    """基于 pHash 距离生产视觉近重复分组。"""

    name = "perceptual_duplicate_group_computer"
    execution_mode = ExecutionMode.DATASET_AGGREGATE
    produced_parameters = frozenset(
        {"perceptual_duplicate_group_id", "perceptual_duplicate_count", "perceptual_duplicate_distance"}
    )
    required_parameters = frozenset({"phash"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        """生产视觉近重复组参数和 pair relation。"""
        max_distance = _as_int(request.config.get("max_distance", 10))
        frame = request.parameter_table[["image_id", "phash"]].copy()
        group_rows, pair_rows = _build_perceptual_groups(frame, max_distance)

        return ParameterResult(
            parameter_updates=pd.DataFrame(group_rows),
            relation_updates={"perceptual_duplicate_pairs": _build_perceptual_duplicate_pairs(pair_rows)},
            artifact_refs={},
            parameter_manifest={
                parameter: {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                    "depends_on": ["phash"],
                    "max_distance": max_distance,
                }
                for parameter in sorted(self.produced_parameters)
            },
        )
```

Add helpers at the bottom of `duplicate.py`:

```python
def _build_perceptual_groups(
    frame: pd.DataFrame,
    max_distance: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """按 pHash 与 keeper 的距离构造近重复组。"""
    groups: list[dict[str, object]] = []
    assignments: list[dict[str, object]] = []
    pairs: list[dict[str, object]] = []

    for row in frame.to_dict(orient="records"):
        image_id = str(row["image_id"])
        phash = str(row.get("phash") or "")
        if not phash:
            assignments.append(
                {
                    "image_id": image_id,
                    "group_index": None,
                    "distance": pd.NA,
                }
            )
            continue

        best_group_index: int | None = None
        best_distance: int | None = None
        for index, group in enumerate(groups):
            distance = _hamming_distance(phash, str(group["keeper_phash"]))
            if distance <= max_distance and (best_distance is None or distance < best_distance):
                best_group_index = index
                best_distance = distance

        if best_group_index is None:
            groups.append({"keeper_image_id": image_id, "keeper_phash": phash, "members": [image_id]})
            assignments.append({"image_id": image_id, "group_index": len(groups) - 1, "distance": 0})
            continue

        group = groups[best_group_index]
        group["members"].append(image_id)
        assignments.append({"image_id": image_id, "group_index": best_group_index, "distance": best_distance})
        pairs.append(
            {
                "source_image_id": group["keeper_image_id"],
                "target_image_id": image_id,
                "distance": int(best_distance),
                "group_id": f"perceptual-{group['keeper_phash']}",
            }
        )

    rows: list[dict[str, object]] = []
    for assignment in assignments:
        group_index = assignment["group_index"]
        if group_index is None:
            rows.append(
                {
                    "image_id": assignment["image_id"],
                    "perceptual_duplicate_group_id": "",
                    "perceptual_duplicate_count": 1,
                    "perceptual_duplicate_distance": pd.NA,
                }
            )
            continue
        group = groups[int(group_index)]
        count = len(group["members"])
        group_id = f"perceptual-{group['keeper_phash']}" if count > 1 else ""
        rows.append(
            {
                "image_id": assignment["image_id"],
                "perceptual_duplicate_group_id": group_id,
                "perceptual_duplicate_count": count,
                "perceptual_duplicate_distance": assignment["distance"] if count > 1 else pd.NA,
            }
        )
    return rows, pairs


def _build_perceptual_duplicate_pairs(pair_rows: list[dict[str, object]]) -> pd.DataFrame:
    """构造视觉近重复 pair relation。"""
    created_at = datetime.now(timezone.utc).isoformat()
    rows = [
        {
            "relation_type": "perceptual_duplicate",
            "source_image_id": pair["source_image_id"],
            "target_image_id": pair["target_image_id"],
            "score": 1.0 - float(pair["distance"]) / 64.0,
            "group_id": pair["group_id"],
            "parameter_name": "perceptual_duplicate_group_id",
            "computer_name": "perceptual_duplicate_group_computer",
            "artifact_ref": "",
            "created_at": created_at,
        }
        for pair in pair_rows
    ]
    return pd.DataFrame(
        rows,
        columns=[
            "relation_type",
            "source_image_id",
            "target_image_id",
            "score",
            "group_id",
            "parameter_name",
            "computer_name",
            "artifact_ref",
            "created_at",
        ],
    )


def _hamming_distance(left: str, right: str) -> int:
    """计算两个 16 位十六进制 pHash 的 Hamming distance。"""
    return (int(left, 16) ^ int(right, 16)).bit_count()


def _as_int(value: object) -> int:
    """把配置值转换为 int。"""
    if isinstance(value, (str, bytes, int, float)):
        return int(value)
    raise TypeError(f"expected int-compatible config value, got {type(value).__name__}")
```

- [ ] **Step 4: Run duplicate computer tests and verify pass**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_duplicate_computer.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/image_gallery/operators/computers/duplicate.py tests/unit/operators/test_duplicate_computer.py
git commit -m "feat: add perceptual duplicate grouping"
```

---

### Task 3: Register Logical Operator and Evaluator

**Files:**
- Modify: `src/image_gallery/operators/builtin.py`
- Modify: `tests/unit/operators/test_builtin_specs.py`
- Modify: `tests/unit/cleaning/test_planner.py`

**Interfaces:**
- Consumes:
  - `phash`
  - `perceptual_duplicate_group_id`
  - `perceptual_duplicate_count`
  - `perceptual_duplicate_distance`
- Produces:
  - built-in operator `duplicate.perceptual_duplicate_check`
  - evaluator `evaluate_perceptual_duplicate_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame`

- [ ] **Step 1: Write failing built-in registry and evaluator tests**

Modify `tests/unit/operators/test_builtin_specs.py` expected operators list:

```python
assert registry.list_operators() == [
    "content.blank_image_check",
    "duplicate.exact_duplicate_check",
    "duplicate.perceptual_duplicate_check",
    "format.decode_check",
    "quality.blur_check",
    "quality.brightness_check",
    "quality.contrast_check",
    "size.aspect_ratio_check",
    "size.dimension_check",
    "size.megapixel_check",
]
```

Add:

```python
def test_perceptual_duplicate_spec_declares_required_parameters() -> None:
    registry = create_default_registry()

    spec = registry.get_operator("duplicate.perceptual_duplicate_check")

    assert spec.required_parameters == [
        "perceptual_duplicate_group_id",
        "perceptual_duplicate_count",
        "perceptual_duplicate_distance",
    ]
    assert spec.evaluation_columns == [
        "perceptual_duplicate_group_id",
        "perceptual_duplicate_count",
        "perceptual_duplicate_distance",
        "perceptual_duplicate_action",
        "perceptual_duplicate_reason",
    ]


def test_perceptual_duplicate_evaluator_drops_non_first_group_members() -> None:
    registry = create_default_registry()
    frame = pd.DataFrame(
        {
            "image_id": ["first", "second", "unique"],
            "perceptual_duplicate_group_id": ["perceptual-a", "perceptual-a", ""],
            "perceptual_duplicate_count": [2, 2, 1],
            "perceptual_duplicate_distance": [0, 3, pd.NA],
        }
    )

    result = registry.get_operator("duplicate.perceptual_duplicate_check").evaluate(
        frame,
        {"max_distance": 10, "keep": "first", "action": "drop"},
    )

    assert result["perceptual_duplicate_action"].tolist() == ["keep", "drop", "keep"]
    assert result.loc[1, "perceptual_duplicate_reason"] == "duplicate in group perceptual-a distance 3"
```

Add to `tests/unit/cleaning/test_planner.py`:

```python
from image_gallery.operators.builtin import create_default_registry


def test_builtin_planner_expands_perceptual_duplicate_dependencies() -> None:
    parsed = parse_operator_configs([{"duplicate.perceptual_duplicate_check": {}}])

    plan = CleaningRunPlanner(create_default_registry()).compile(parsed)

    assert [step.computer_name for step in plan.parameter_plan.steps] == [
        "image_perceptual_hash_computer",
        "perceptual_duplicate_group_computer",
    ]
    assert plan.parameter_plan.steps[0].requested_parameters == frozenset({"phash"})
    assert plan.parameter_plan.steps[1].requested_parameters == frozenset(
        {
            "perceptual_duplicate_group_id",
            "perceptual_duplicate_count",
            "perceptual_duplicate_distance",
        }
    )
```

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_builtin_specs.py tests/unit/cleaning/test_planner.py -q
```

Expected: FAIL because the new operator and computers are not registered.

- [ ] **Step 3: Register computers and operator**

Modify imports in `src/image_gallery/operators/builtin.py`:

```python
from image_gallery.operators.computers.duplicate import DuplicateGroupComputer, PerceptualDuplicateGroupComputer
from image_gallery.operators.computers.hash import ImageHashComputer, ImagePerceptualHashComputer
```

Modify `create_default_registry()`:

```python
registry.register_parameter_computer(ImageHashComputer())
registry.register_parameter_computer(ImagePerceptualHashComputer())
registry.register_parameter_computer(DuplicateGroupComputer())
registry.register_parameter_computer(PerceptualDuplicateGroupComputer())
```

Add this `OperatorSpec` after `duplicate.exact_duplicate_check`:

```python
OperatorSpec(
    name="duplicate.perceptual_duplicate_check",
    category="duplicate",
    required_parameters=[
        "perceptual_duplicate_group_id",
        "perceptual_duplicate_count",
        "perceptual_duplicate_distance",
    ],
    evaluation_columns=[
        "perceptual_duplicate_group_id",
        "perceptual_duplicate_count",
        "perceptual_duplicate_distance",
        "perceptual_duplicate_action",
        "perceptual_duplicate_reason",
    ],
    default_config={"max_distance": 10, "keep": "first", "action": "drop"},
    action_column="perceptual_duplicate_action",
    reason_column="perceptual_duplicate_reason",
    evaluator=evaluate_perceptual_duplicate_check,
),
```

Add evaluator after `evaluate_exact_duplicate_check()`:

```python
def evaluate_perceptual_duplicate_check(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    """根据视觉近重复组生成去重结果。"""
    keep = str(config.get("keep", "first"))
    if keep != "first":
        raise ValueError("duplicate.perceptual_duplicate_check only supports keep='first'")
    action = str(config.get("action", "drop"))
    if action != "drop":
        raise ValueError("duplicate.perceptual_duplicate_check only supports action='drop'")

    groups = parameter_table["perceptual_duplicate_group_id"].fillna("").astype(str)
    counts = pd.to_numeric(parameter_table["perceptual_duplicate_count"], errors="coerce").fillna(1).astype(int)
    distances = pd.to_numeric(parameter_table["perceptual_duplicate_distance"], errors="coerce")

    seen_groups: set[str] = set()
    actions: list[str] = []
    reasons: list[str] = []
    for group_id, count, distance in zip(groups.tolist(), counts.tolist(), distances.tolist(), strict=True):
        if not group_id or count <= 1:
            actions.append("keep")
            reasons.append("")
            continue
        if group_id not in seen_groups:
            seen_groups.add(group_id)
            actions.append("keep")
            reasons.append("")
            continue
        actions.append(action)
        reasons.append(f"duplicate in group {group_id} distance {int(distance)}")

    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "perceptual_duplicate_group_id": groups,
            "perceptual_duplicate_count": counts,
            "perceptual_duplicate_distance": distances,
            "perceptual_duplicate_action": actions,
            "perceptual_duplicate_reason": reasons,
        }
    )
```

- [ ] **Step 4: Run focused tests and verify pass**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_builtin_specs.py tests/unit/cleaning/test_planner.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/image_gallery/operators/builtin.py tests/unit/operators/test_builtin_specs.py tests/unit/cleaning/test_planner.py
git commit -m "feat: register perceptual duplicate operator"
```

---

### Task 4: Wire Integration Config and BasicCleaner Smoke Coverage

**Files:**
- Modify: `notebooks/_helpers/cleaning_configs.py`
- Modify: `tests/integration/cleaning/test_basic_cleaner_builtin_run.py`

**Interfaces:**
- Consumes: built-in `duplicate.perceptual_duplicate_check`
- Produces:
  - shared first-batch config includes perceptual duplicate operator.
  - integration run writes `phash`, `perceptual_duplicate_*`, and `relations/perceptual_duplicate_pairs.parquet`.

- [ ] **Step 1: Write failing integration assertions**

Modify `notebooks/_helpers/cleaning_configs.py` to include the new operator after exact duplicate:

```python
{"duplicate.exact_duplicate_check": {}},
{"duplicate.perceptual_duplicate_check": {}},
```

Modify local integration cleaner config in `tests/integration/cleaning/test_basic_cleaner_builtin_run.py`:

```python
{"duplicate.exact_duplicate_check": {}},
{"duplicate.perceptual_duplicate_check": {}},
```

Add assertions in `test_basic_cleaner_runs_first_batch_builtin_operators()`:

```python
assert rows.loc["dupe", "perceptual_duplicate_action"] == "drop"
```

Add expected parameter columns:

```python
"phash",
"perceptual_duplicate_group_id",
"perceptual_duplicate_count",
"perceptual_duplicate_distance",
```

Add relation assertion:

```python
assert (run_dir / "relations" / "perceptual_duplicate_pairs.parquet").exists()
```

Modify the sample_1000 expected parameter columns:

```python
"phash",
"perceptual_duplicate_group_id",
"perceptual_duplicate_count",
"perceptual_duplicate_distance",
```

Modify the sample_1000 expected evaluation columns:

```python
"perceptual_duplicate_action",
"perceptual_duplicate_reason",
```

Add relation assertion in sample_1000 test:

```python
assert (run_dir / "relations" / "perceptual_duplicate_pairs.parquet").exists()
```

- [ ] **Step 2: Run integration test and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/integration/cleaning/test_basic_cleaner_builtin_run.py::test_basic_cleaner_runs_first_batch_builtin_operators -q
```

Expected: FAIL until Task 1-3 are implemented; after Task 1-3, this should pass.

- [ ] **Step 3: Adjust assertions only if pHash threshold behavior differs on fixture images**

If the local fixture image pair is exact byte duplicate, it must be a pHash duplicate and `dupe` must drop. Do not loosen this assertion. If it fails, inspect `parameter_table.parquet` and fix the pHash/grouping implementation instead of weakening the test.

- [ ] **Step 4: Run integration test and verify pass**

Run:

```bash
.venv/bin/python -m pytest tests/integration/cleaning/test_basic_cleaner_builtin_run.py::test_basic_cleaner_runs_first_batch_builtin_operators -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add notebooks/_helpers/cleaning_configs.py tests/integration/cleaning/test_basic_cleaner_builtin_run.py
git commit -m "test: cover perceptual duplicate cleaner run"
```

---

### Task 5: Full Verification and Cleanup

**Files:**
- Inspect: all files changed by Tasks 1-4.

**Interfaces:**
- Consumes: all implemented pHash duplicate behavior.
- Produces: verified branch with no lint/type/test regressions.

- [ ] **Step 1: Run operator and cleaning tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators tests/unit/cleaning tests/integration/cleaning -q
```

Expected: PASS, with sample_1000 integration allowed to skip only when the local MinIO sample or credentials are unavailable.

- [ ] **Step 2: Run ruff**

Run:

```bash
.venv/bin/python -m ruff check src/image_gallery tests/unit/operators tests/unit/cleaning tests/integration/cleaning notebooks/_helpers
```

Expected: `All checks passed!`

- [ ] **Step 3: Run mypy**

Run:

```bash
.venv/bin/python -m mypy src/image_gallery
```

Expected: `Success: no issues found`.

- [ ] **Step 4: Inspect git diff for scope**

Run:

```bash
git status --short
git diff --stat HEAD
```

Expected:

- Only pHash duplicate operator files, tests, and shared helper config changed.
- Existing user notebook changes remain uncommitted unless the user explicitly asks to include them.

- [ ] **Step 5: Final commit if verification fixes were needed**

If verification required additional fixes, commit them:

```bash
git add src/image_gallery/operators tests/unit/operators tests/unit/cleaning tests/integration/cleaning notebooks/_helpers
git commit -m "fix: finalize perceptual duplicate operator"
```

If no fixes were needed after Task 4, do not create an empty commit.
