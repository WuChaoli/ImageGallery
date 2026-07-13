# Cleaning User Experience Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将图片清洗包调整为用户友好的 recipe 驱动、短名算子、非阻塞运行、可停止/恢复/查询进度、可控存储和一致 Dataset 导出契约。

**Architecture:** 先把内置逻辑算子的主标识从 `category.operator_check` 迁移为短名，再让 YAML recipe 直接使用短名。`run()` 改为非阻塞并返回 `CleanerRun`，同步行为通过 `run_sync()` 提供；运行状态通过 `RunStore` 承载，第一阶段支持 `memory | temporary | disk` 三种模式。阈值配置按用户心智分流：尺寸等自然单位使用绝对值，主观质量分使用 0-1 区间，布尔/分组类使用动作规则。

**Tech Stack:** Python 3.10, pandas, pyarrow/parquet, SQLite, pytest, ruff, mypy, YAML, existing `src/image_gallery` package.

## Global Constraints

- 交流文档使用简体中文；代码文件、目录、代码命名使用 English。
- 保持 V1 local-first 边界，不引入服务端 API、Web UI、分布式调度器或训练数据导出节点。
- 算子主标识统一使用短名，例如 `blur`、`dimension`、`exact_duplicate`；不再把 `quality.blur_check` 作为主流程名称。
- 不保留旧长名兼容；当前处于开发阶段，允许破坏式清理接口。
- YAML 是用户友好 recipe，不是内部 `CleanerConfig` 的 YAML 版。
- `run()` / `resume()` 非阻塞，返回 `CleanerRun`；`run_sync()` / `resume_sync()` 阻塞，返回 `CleanerResult`。
- 不新增 `run_and_export` 这类一键运行导出 API；一键导出只通过 `result.export("ALL")` 表达。
- 清洗结果导出返回 `Dataset`，默认列与输入 Dataset 保持一致；计算/评估列必须由用户显式选择保留。
- 语义检测必须依赖模型，不支持 `require_model=false`；缺依赖时在 compile/dry-run/check 阶段给出 warning 或 error。
- 第一阶段运行存储支持 `memory | temporary | disk`，默认 `temporary`；暂不实现复杂 `hybrid`。
- 重复图保留策略增强是后续建议，本轮不实现。

---

## File Structure

- Modify: `src/image_gallery/operators/builtin.py`
  - 将内置 `OperatorSpec.name` 全部迁移为短名。
  - 补充用户规则、阈值元数据和 preview policy 的短名映射。
- Modify: `src/image_gallery/operators/spec.py`
  - 增加算子用户规则元数据、阈值/指标元数据。
- Modify: `src/image_gallery/cleaning/selection.py`
  - 移除对长名的依赖，支持短名和 category 选择。
- Create: `src/image_gallery/cleaning/recipe.py`
  - 解析 YAML recipe，编译为短名算子选择和用户规则配置。
- Create: `src/image_gallery/cleaning/rules.py`
  - 解析区间规则，例如 `"[0, 0.3]"`、`"(0.3, 0.6]"`。
- Create: `src/image_gallery/cleaning/thresholds.py`
  - 将相对区间映射到绝对指标值。
- Create: `src/image_gallery/cleaning/run_handle.py`
  - 定义 `CleanerRun`、`RunProgress`、运行错误类型。
- Create: `src/image_gallery/cleaning/run_store.py`
  - 定义 `RunStore` 抽象和 `MemoryRunStore`、`TemporaryRunStore`、`DiskRunStore`。
- Modify: `src/image_gallery/cleaning/basic.py`
  - `run()` 改为非阻塞返回 `CleanerRun`，新增 `run_sync()`。
  - 增加 `from_recipe()`。
- Modify: `src/image_gallery/cleaning/execution.py`
  - `CleanerExecution.run()` 改为非阻塞返回 `CleanerRun`。
  - 增加 `run_sync()`、`resume_sync()`、`get_progress()`。
  - 支持 `output_dir`、`cache_root`、`storage`。
- Modify: `src/image_gallery/cleaning/runtime.py`
  - 支持协作式停止、进度写入、stopped 状态。
- Modify: `src/image_gallery/cleaning/runtime_state.py`
  - 扩展运行状态、stop request、progress 查询。
- Modify: `src/image_gallery/cleaning/result.py`
  - 支持 `export("ALL")`。
  - 增加 `update()` / `apply()`。
  - 调整默认导出列契约。
- Modify: `src/image_gallery/cleaning/export.py`
  - 按输入 Dataset 列构建结果 Dataset 视图。
- Modify: `src/image_gallery/operators/computers/base.py`
  - 增加 `before_run_check()` 默认钩子。
- Modify: `src/image_gallery/operators/computers/semantic.py`
  - 增加语义依赖和模型路径检查。
- Tests:
  - `tests/unit/operators/test_builtin_specs.py`
  - `tests/unit/cleaning/test_selection.py`
  - `tests/unit/cleaning/test_recipe.py`
  - `tests/unit/cleaning/test_rules.py`
  - `tests/unit/cleaning/test_thresholds.py`
  - `tests/unit/cleaning/test_run_handle.py`
  - `tests/unit/cleaning/test_run_store.py`
  - `tests/unit/cleaning/test_run_options.py`
  - `tests/unit/cleaning/test_result_update.py`
  - `tests/unit/cleaning/test_export_all.py`
  - `tests/unit/operators/test_computer_checks.py`
- Docs:
  - `examples/cleaning_recipe.yaml`
  - `examples/README.md`
  - `README.md`

---

### Task 1: 内置算子短名迁移

**Files:**
- Modify: `src/image_gallery/operators/builtin.py`
- Modify: `src/image_gallery/operators/spec.py`
- Modify: `src/image_gallery/cleaning/selection.py`
- Test: `tests/unit/operators/test_builtin_specs.py`
- Test: `tests/unit/cleaning/test_selection.py`
- Update affected existing tests under `tests/unit/cleaning/` and `tests/integration/cleaning/`.

**Interfaces:**
- Produces short operator names:
  - `decode`
  - `dimension`
  - `aspect_ratio`
  - `megapixel`
  - `blur`
  - `brightness`
  - `contrast`
  - `exposure`
  - `noise`
  - `blank`
  - `mono_color`
  - `border_padding`
  - `animated`
  - `orientation`
  - `exact_duplicate`
  - `perceptual_duplicate`
  - `semantic_duplicate`
- Preserves category names: `format`、`size`、`quality`、`content`、`metadata`、`duplicate`。

- [ ] **Step 1: Write failing tests for short builtin names**

```python
from image_gallery.cleaning import BasicCleaner
from image_gallery.operators.builtin import create_default_registry


def test_builtin_operator_names_are_short() -> None:
    registry = create_default_registry()

    assert registry.list_operators() == [
        "animated",
        "aspect_ratio",
        "blank",
        "blur",
        "border_padding",
        "brightness",
        "contrast",
        "decode",
        "dimension",
        "exact_duplicate",
        "exposure",
        "megapixel",
        "mono_color",
        "noise",
        "orientation",
        "perceptual_duplicate",
        "semantic_duplicate",
    ]


def test_basic_cleaner_selects_short_name() -> None:
    plan = BasicCleaner(["blur"]).plan()

    assert plan["node_id"].str.contains("blur").any()


def test_basic_cleaner_selects_category_case_insensitive() -> None:
    plan = BasicCleaner(["quality"]).plan()

    assert plan["node_id"].str.contains("blur").any()
    assert plan["node_id"].str.contains("brightness").any()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/python -m pytest tests/unit/operators/test_builtin_specs.py tests/unit/cleaning/test_selection.py -q`

Expected: FAIL because current builtin names still use long names such as `quality.blur_check`.

- [ ] **Step 3: Rename `OperatorSpec.name` values**

Replace current names:

```text
format.decode_check -> decode
size.dimension_check -> dimension
size.aspect_ratio_check -> aspect_ratio
size.megapixel_check -> megapixel
quality.blur_check -> blur
quality.brightness_check -> brightness
quality.contrast_check -> contrast
quality.exposure_check -> exposure
quality.noise_check -> noise
content.blank_image_check -> blank
content.mono_color_check -> mono_color
content.border_padding_check -> border_padding
format.animated_image_check -> animated
metadata.orientation_check -> orientation
duplicate.exact_duplicate_check -> exact_duplicate
duplicate.perceptual_duplicate_check -> perceptual_duplicate
duplicate.semantic_duplicate_check -> semantic_duplicate
```

Also update preview policy dictionary keys and error messages to use short names.

- [ ] **Step 4: Remove long-name compatibility from selection**

Required behavior:
- `"blur"` selects the blur operator.
- `"quality"` selects all quality category operators.
- `"QUALITY"` still works by case-insensitive category matching.
- `"quality.blur_check"` raises `ValueError`.

- [ ] **Step 5: Update test fixtures and examples**

Replace all test/example configs:

```python
{"quality.blur_check": {"min_score": 100.0}}
```

with:

```python
{"blur": {"min_score": 100.0}}
```

- [ ] **Step 6: Run focused regression**

Run: `.venv/bin/python -m pytest tests/unit/operators tests/unit/cleaning tests/integration/cleaning -q`

Expected: PASS after all short-name references are updated.

---

### Task 2: Recipe YAML 与规则结构

**Files:**
- Create: `src/image_gallery/cleaning/recipe.py`
- Create: `src/image_gallery/cleaning/rules.py`
- Modify: `src/image_gallery/cleaning/basic.py`
- Test: `tests/unit/cleaning/test_recipe.py`
- Test: `tests/unit/cleaning/test_rules.py`
- Docs: `examples/cleaning_recipe.yaml`

**Interfaces:**
- Produces: `CleanerRecipe.from_yaml(path: str | Path) -> CleanerRecipe`
- Produces: `CleanerRecipe.to_operator_selectors() -> list[str | dict[str, dict[str, object]]]`
- Produces: `BasicCleaner.from_recipe(path: str | Path) -> BasicCleaner`
- Produces: `ActionRange.parse(value: str) -> ActionRange`

- [ ] **Step 1: Write failing tests for interval parsing**

```python
from image_gallery.cleaning.rules import ActionRange


def test_action_range_parses_open_closed_interval() -> None:
    parsed = ActionRange.parse("(0.3, 0.6]")

    assert parsed.lower == 0.3
    assert parsed.upper == 0.6
    assert parsed.lower_inclusive is False
    assert parsed.upper_inclusive is True
    assert parsed.contains(0.3) is False
    assert parsed.contains(0.6) is True


def test_action_range_rejects_invalid_interval() -> None:
    try:
        ActionRange.parse("0.3,0.6")
    except ValueError as exc:
        assert "invalid interval" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Write failing tests for recipe shape**

```python
from pathlib import Path

from image_gallery.cleaning import BasicCleaner
from image_gallery.cleaning.recipe import CleanerRecipe


def test_recipe_loads_short_operator_rules_and_run_defaults(tmp_path: Path) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    recipe_path.write_text(
        """
version: 1
run:
  output_dir: ./outputs/cleaning
  cache_root: ./.cache/image-gallery
  storage: temporary
operators:
  - use: decode
    action: drop
  - use: dimension
    drop:
      min_width: 256
      min_height: 256
    review:
      min_width: 512
      min_height: 512
  - use: blur
    rules:
      drop: "[0, 0.3]"
      review: "(0.3, 0.6]"
""".strip(),
        encoding="utf-8",
    )

    recipe = CleanerRecipe.from_yaml(recipe_path)

    assert recipe.version == 1
    assert recipe.run_defaults["storage"] == "temporary"
    assert recipe.operators[0]["use"] == "decode"
    assert recipe.operators[2]["rules"]["drop"] == "[0, 0.3]"


def test_basic_cleaner_from_recipe_compiles_short_names(tmp_path: Path) -> None:
    recipe_path = tmp_path / "recipe.yaml"
    recipe_path.write_text(
        """
version: 1
operators:
  - use: decode
    action: drop
""".strip(),
        encoding="utf-8",
    )

    cleaner = BasicCleaner.from_recipe(recipe_path)

    assert cleaner.plan()["node_id"].str.contains("decode").any()
```

- [ ] **Step 3: Run tests to verify failure**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_rules.py tests/unit/cleaning/test_recipe.py -q`

Expected: FAIL because recipe/rules modules do not exist.

- [ ] **Step 4: Implement `ActionRange` parser**

Implement:

```python
@dataclass(frozen=True)
class ActionRange:
    """用户 recipe 中的动作区间。"""

    lower: float
    upper: float
    lower_inclusive: bool
    upper_inclusive: bool

    @classmethod
    def parse(cls, value: str) -> "ActionRange": ...

    def contains(self, value: float) -> bool: ...
```

Supported syntax:
- `[0, 0.3]`
- `(0.3, 0.6]`
- `[0.6, 1)`

Do not support infinity in first version.

- [ ] **Step 5: Implement recipe parser**

YAML shape:

```yaml
version: 1

run:
  output_dir: ./outputs/cleaning
  cache_root: ./.cache/image-gallery
  storage: temporary

operators:
  - use: decode
    action: drop

  - use: dimension
    drop:
      min_width: 256
      min_height: 256
    review:
      min_width: 512
      min_height: 512

  - use: blur
    rules:
      drop: "[0, 0.3]"
      review: "(0.3, 0.6]"
```

Validation:
- `version` defaults to `1` and must equal `1`.
- `operators` must be a non-empty list.
- Each operator must contain non-empty string `use`.
- `run.storage` if present must be `memory`、`temporary`、`disk`。

- [ ] **Step 6: Compile recipe to operator selectors**

Initial compilation rule:
- `use` becomes operator short name.
- `action` passes through for boolean/group operators.
- `drop` / `review` absolute rule blocks pass through as `drop` / `review`.
- `rules` interval blocks pass through as `rules`.

Example output:

```python
[
    {"decode": {"action": "drop"}},
    {
        "dimension": {
            "drop": {"min_width": 256, "min_height": 256},
            "review": {"min_width": 512, "min_height": 512},
        }
    },
    {"blur": {"rules": {"drop": "[0, 0.3]", "review": "(0.3, 0.6]"}}},
]
```

- [ ] **Step 7: Add example recipe**

Create `examples/cleaning_recipe.yaml` with the YAML shape above plus `exact_duplicate` and `brightness`.

- [ ] **Step 8: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_rules.py tests/unit/cleaning/test_recipe.py -q`

Expected: PASS.

---

### Task 3: 阈值/指标元数据与双级动作评估

**Files:**
- Create: `src/image_gallery/cleaning/thresholds.py`
- Modify: `src/image_gallery/operators/spec.py`
- Modify: `src/image_gallery/operators/builtin.py`
- Test: `tests/unit/cleaning/test_thresholds.py`
- Test: `tests/unit/operators/test_builtin_specs.py`

**Interfaces:**
- Produces: `MetricSpec`
- Produces: `MetricValueType = "absolute" | "relative" | "categorical"`
- Produces: `MetricDirection = "higher_better" | "lower_better" | "range_best" | "categorical"`
- Produces: `relative_to_absolute(metric: MetricSpec, value: float) -> float`

- [ ] **Step 1: Write failing tests for metric mapping**

```python
from image_gallery.cleaning.thresholds import MetricSpec, relative_to_absolute


def test_relative_metric_maps_midpoint_to_absolute_midpoint() -> None:
    metric = MetricSpec(
        name="blur_score",
        value_type="relative",
        absolute_min=0.0,
        absolute_max=300.0,
        direction="higher_better",
    )

    assert relative_to_absolute(metric, 0.5) == 150.0


def test_relative_metric_rejects_out_of_range_value() -> None:
    metric = MetricSpec(
        name="noise_score",
        value_type="relative",
        absolute_min=0.0,
        absolute_max=1.0,
        direction="lower_better",
    )

    try:
        relative_to_absolute(metric, 1.1)
    except ValueError as exc:
        assert "relative value must be between 0 and 1" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Write failing tests for two-level actions**

```python
from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


def test_blur_rules_can_emit_drop_and_review(tmp_path: Path) -> None:
    image_path = tmp_path / "flat.png"
    Image.new("RGB", (16, 16), color=(120, 120, 120)).save(image_path)
    dataset = Dataset.write(
        pd.DataFrame({"image_id": ["flat"], "image_uri": [str(image_path)]}),
        str(tmp_path / "raw.parquet"),
    )

    result = BasicCleaner(
        [{"blur": {"rules": {"drop": "[0, 0.3]", "review": "(0.3, 0.6]"}}}]
    ).run_sync(dataset)

    row = result.export("full", tmp_path / "full.parquet", include_columns=["blur_action"]).to_frame().iloc[0]
    assert row["blur_action"] in {"drop", "review", "keep"}
```

- [ ] **Step 3: Run tests to verify failure**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_thresholds.py -q`

Expected: FAIL because metric mapping does not exist.

- [ ] **Step 4: Implement metric model**

```python
@dataclass(frozen=True)
class MetricSpec:
    """逻辑算子的用户可调指标定义。"""

    name: str
    value_type: Literal["absolute", "relative", "categorical"]
    absolute_min: float | None = None
    absolute_max: float | None = None
    direction: Literal["higher_better", "lower_better", "range_best", "categorical"] = "categorical"
```

- [ ] **Step 5: Add builtin metric metadata**

Initial metadata:

```text
dimension: absolute, width/height natural unit
megapixel: absolute, megapixels natural unit
aspect_ratio: absolute, ratio natural unit
blur: relative, blur_score 0..300, higher_better
brightness: relative, brightness_score 0..255, range_best
contrast: relative, contrast_score 0..128, higher_better
noise: relative, noise_score 0..1, lower_better
blank: relative, blank_score 0..1, lower_better
mono_color: relative, mono_color_score 0..1, lower_better
border_padding: relative, border_padding_ratio 0..1, lower_better
semantic_duplicate: relative, semantic_duplicate_score 0..1, lower_better for duplicate risk
decode/exact_duplicate/perceptual_duplicate/animated/orientation: categorical or absolute custom
```

- [ ] **Step 6: Update evaluators for `drop` / `review` rule blocks**

Required behavior:
- If `rules` exists for relative metric operators, evaluate intervals in priority order `drop > review > keep`.
- If `drop` / `review` absolute blocks exist for natural-unit operators, evaluate `drop` first, then `review`.
- Existing absolute config keys can be removed or updated by tests during migration; no long-term compatibility required.

- [ ] **Step 7: Run focused tests**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_thresholds.py tests/unit/operators/test_builtin_specs.py tests/integration/cleaning/test_basic_cleaner_builtin_run.py -q`

Expected: PASS.

---

### Task 4: RunStore 存储模式

**Files:**
- Create: `src/image_gallery/cleaning/run_store.py`
- Modify: `src/image_gallery/cleaning/execution.py`
- Modify: `src/image_gallery/cleaning/runtime.py`
- Modify: `src/image_gallery/cleaning/result.py`
- Test: `tests/unit/cleaning/test_run_store.py`

**Interfaces:**
- Produces: `RunStorageMode = "memory" | "temporary" | "disk"`
- Produces: `RunStore`
- Produces: `MemoryRunStore`
- Produces: `TemporaryRunStore`
- Produces: `DiskRunStore`

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path

import pandas as pd

from image_gallery.cleaning.run_store import MemoryRunStore, TemporaryRunStore


def test_memory_run_store_round_trips_table() -> None:
    store = MemoryRunStore(run_id="run-1")
    frame = pd.DataFrame({"image_id": ["a"]})

    store.write_table("evaluation", frame)

    assert store.read_table("evaluation").equals(frame)


def test_temporary_run_store_cleans_up() -> None:
    store = TemporaryRunStore(run_id="run-1")
    root = store.root

    store.write_table("evaluation", pd.DataFrame({"image_id": ["a"]}))
    assert root.exists()

    store.cleanup()

    assert not root.exists()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_run_store.py -q`

Expected: FAIL because run store module does not exist.

- [ ] **Step 3: Implement minimal store abstraction**

Required methods:

```python
class RunStore(Protocol):
    run_id: str
    root: Path | None

    def write_table(self, name: str, frame: pd.DataFrame) -> None: ...
    def read_table(self, name: str) -> pd.DataFrame: ...
    def write_json(self, name: str, payload: object) -> None: ...
    def read_json(self, name: str) -> object: ...
    def materialize_dataset(self, name: str, frame: pd.DataFrame, storage: Storage | None = None) -> Dataset: ...
    def cleanup(self) -> None: ...
```

- [ ] **Step 4: Define storage mode behavior**

`memory`:
- Tables and JSON stay in process memory.
- Exported Dataset materialization may use temporary parquet because `Dataset` currently points to a file path.
- No cross-process resume guarantee.

`temporary`:
- Tables/JSON/Dataset files use a temp directory.
- Default mode.
- Cleanup removes temp directory.

`disk`:
- Uses `cache_root / run_id`.
- Supports long-lived resume/debug.

Semantic embeddings/Faiss:
- Always require filesystem path.
- In `memory` mode, semantic operators must emit a check error asking user to use `temporary` or `disk`.

- [ ] **Step 5: Wire `storage` run option**

Supported values:

```python
storage="memory"
storage="temporary"
storage="disk"
```

Default: `temporary`.

- [ ] **Step 6: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_run_store.py tests/unit/cleaning/test_run_options.py -q`

Expected: PASS.

---

### Task 5: 非阻塞 `run()`、`CleanerRun`、stop/progress/resume

**Files:**
- Create: `src/image_gallery/cleaning/run_handle.py`
- Modify: `src/image_gallery/cleaning/basic.py`
- Modify: `src/image_gallery/cleaning/execution.py`
- Modify: `src/image_gallery/cleaning/runtime.py`
- Modify: `src/image_gallery/cleaning/runtime_state.py`
- Test: `tests/unit/cleaning/test_run_handle.py`
- Test: `tests/integration/cleaning/test_cleaner_runtime_resume.py`

**Interfaces:**
- Produces: `CleanerRun`
- Produces: `RunProgress`
- Produces: `CleanerRunNotReadyError`
- Produces: `CleanerRunFailedError`
- Updates: `BasicCleaner.run() -> CleanerRun`
- Adds: `BasicCleaner.run_sync() -> CleanerResult`
- Updates: `CleanerExecution.run() -> CleanerRun`
- Adds: `CleanerExecution.run_sync() -> CleanerResult`
- Updates: `CleanerExecution.resume() -> CleanerRun`
- Adds: `CleanerExecution.resume_sync() -> CleanerResult`

- [ ] **Step 1: Write failing tests for non-blocking run contract**

```python
from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.cleaning.run_handle import CleanerRun
from image_gallery.dataset import Dataset


def _dataset(tmp_path: Path) -> Dataset:
    image_path = tmp_path / "ok.png"
    Image.new("RGB", (8, 8), color=(10, 20, 30)).save(image_path)
    return Dataset.write(
        pd.DataFrame({"image_id": ["ok"], "image_uri": [str(image_path)]}),
        str(tmp_path / "raw.parquet"),
    )


def test_run_returns_handle_and_wait_returns_result(tmp_path: Path) -> None:
    run = BasicCleaner(["decode"]).run(_dataset(tmp_path), run_id="run-1")

    assert isinstance(run, CleanerRun)
    result = run.wait(timeout=10)

    assert result.run_id == "run-1"


def test_run_sync_returns_result(tmp_path: Path) -> None:
    result = BasicCleaner(["decode"]).run_sync(_dataset(tmp_path), run_id="run-1")

    assert result.run_id == "run-1"
```

- [ ] **Step 2: Write failing tests for progress**

```python
def test_run_progress_reports_percent(tmp_path: Path) -> None:
    run = BasicCleaner(["decode"]).run(_dataset(tmp_path), run_id="run-1")
    result = run.wait(timeout=10)

    progress = run.get_progress()

    assert progress.run_id == result.run_id
    assert progress.status == "completed"
    assert progress.percent == 100.0
```

- [ ] **Step 3: Run tests to verify failure**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_run_handle.py -q`

Expected: FAIL because `CleanerRun` does not exist and `run()` still returns `CleanerResult`.

- [ ] **Step 4: Implement `CleanerRun` with background worker**

Required behavior:
- `run()` starts a daemon or managed worker thread.
- Worker calls existing synchronous runtime path.
- `wait(timeout)` joins worker and returns `CleanerResult` on completed status.
- `result(partial=False)` returns completed result or raises if not ready.
- Exceptions raised by worker are captured and re-raised as `CleanerRunFailedError`.

- [ ] **Step 5: Implement progress model**

```python
@dataclass(frozen=True)
class RunProgress:
    run_id: str
    status: str
    processed: int
    total: int
    percent: float
    current_node: str | None
    node_progress: dict[str, NodeProgress]
```

For first pass:
- Use state records already written by runtime.
- If total is zero, percent is `0.0` unless completed, then `100.0`.

- [ ] **Step 6: Implement stop request**

Required behavior:
- `CleanerRun.stop()` records a stop request.
- Runtime checks stop request at node or batch boundary.
- Status flow: `running -> stopping -> stopped`.
- `run.result()` on stopped raises unless `partial=True`.

- [ ] **Step 7: Implement resume non-blocking wrappers**

Required behavior:
- `resume()` returns `CleanerRun`.
- `resume_sync()` returns `CleanerResult`.
- Existing resume validation remains.

- [ ] **Step 8: Run regression**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_run_handle.py tests/integration/cleaning/test_cleaner_runtime_resume.py tests/integration/cleaning/test_cleaner_runtime_lifecycle.py -q`

Expected: PASS after old tests are migrated to `run_sync()` or `.run(...).wait()`.

---

### Task 6: `output_dir`、`cache_root` 和未知运行参数校验

**Files:**
- Modify: `src/image_gallery/cleaning/basic.py`
- Modify: `src/image_gallery/cleaning/execution.py`
- Test: `tests/unit/cleaning/test_run_options.py`

**Interfaces:**
- Consumes: `RunStore` from Task 4 and `CleanerRun` from Task 5.
- Supports run options:
  - `run_id`
  - `retry_max_attempts`
  - `sample`
  - `progress`
  - `label`
  - `tags`
  - `output_dir`
  - `cache_root`
  - `storage`

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


def _dataset(tmp_path: Path) -> Dataset:
    image_path = tmp_path / "ok.png"
    Image.new("RGB", (8, 8), color=(10, 20, 30)).save(image_path)
    return Dataset.write(
        pd.DataFrame({"image_id": ["ok"], "image_uri": [str(image_path)]}),
        str(tmp_path / "raw.parquet"),
    )


def test_run_supports_output_dir_and_cache_root(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    output_dir = tmp_path / "runs"
    cache_root = tmp_path / "cache"

    result = BasicCleaner(["decode"]).run_sync(
        dataset,
        output_dir=output_dir,
        cache_root=cache_root,
        storage="disk",
        run_id="run-1",
    )

    assert result.run_id == "run-1"
    assert (cache_root / "run-1").exists()
    assert output_dir.exists()


def test_run_rejects_unknown_options(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)

    try:
        BasicCleaner(["decode"]).run_sync(dataset, output_dir_typo=tmp_path)
    except TypeError as exc:
        assert "unsupported run option" in str(exc)
    else:
        raise AssertionError("expected TypeError")
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_run_options.py -q`

Expected: FAIL until options are validated and path semantics are wired.

- [ ] **Step 3: Implement supported run option validation**

Add `SUPPORTED_RUN_OPTIONS` and reject unknown keys before starting worker thread.

- [ ] **Step 4: Define path defaults**

Default behavior:
- `storage` default is `temporary`.
- `cache_root` default remains `~/.cache/image_gallery/cleaning/runs` for `disk`.
- `output_dir` default is `None`; no user-visible copy is created unless export or explicit output is requested.
- If recipe provides run defaults, explicit `run()` options override recipe defaults.

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_run_options.py -q`

Expected: PASS.

---

### Task 7: Result Dataset 导出、`export("ALL")`、`update()` / `apply()`

**Files:**
- Modify: `src/image_gallery/cleaning/export.py`
- Modify: `src/image_gallery/cleaning/result.py`
- Test: `tests/unit/cleaning/test_export_all.py`
- Test: `tests/unit/cleaning/test_result_update.py`

**Interfaces:**
- Produces: `CleanerResult.export("ALL", output_dir, include_columns: list[str] | None = None) -> dict[str, Dataset]`
- Updates: `CleanerResult.export(kind, path, include_columns=None) -> Dataset`
- Produces: `CleanerResult.update(frame: pd.DataFrame, on: str = "image_id", columns: list[str] | None = None) -> CleanerResult`
- Produces: `CleanerResult.apply(frame: pd.DataFrame, on: str = "image_id", columns: list[str] | None = None) -> CleanerResult`

- [ ] **Step 1: Write failing export tests**

```python
from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning import BasicCleaner
from image_gallery.dataset import Dataset


def _dataset(tmp_path: Path) -> Dataset:
    ok = tmp_path / "ok.png"
    bad = tmp_path / "bad.jpg"
    Image.new("RGB", (8, 8), color=(10, 20, 30)).save(ok)
    bad.write_bytes(b"not an image")
    return Dataset.write(
        pd.DataFrame(
            {
                "image_id": ["ok", "bad"],
                "image_uri": [str(ok), str(bad)],
                "source_uri": ["a", "b"],
            }
        ),
        str(tmp_path / "raw.parquet"),
    )


def test_export_clean_preserves_input_columns_by_default(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    result = BasicCleaner([{"decode": {"action": "drop"}}]).run_sync(dataset, run_id="run-1")

    clean = result.export("clean", tmp_path / "clean.parquet")

    assert clean.storage is dataset.storage
    assert clean.to_frame().columns.tolist() == ["image_id", "image_uri", "source_uri"]


def test_export_can_include_evaluation_columns(tmp_path: Path) -> None:
    result = BasicCleaner([{"decode": {"action": "drop"}}]).run_sync(_dataset(tmp_path), run_id="run-1")

    clean = result.export("clean", tmp_path / "clean.parquet", include_columns=["final_action", "decode_reason"])

    assert {"final_action", "decode_reason"}.issubset(clean.to_frame().columns)


def test_export_all_writes_standard_views(tmp_path: Path) -> None:
    result = BasicCleaner([{"decode": {"action": "drop"}}]).run_sync(_dataset(tmp_path), run_id="run-1")

    exported = result.export("ALL", tmp_path / "exports")

    assert sorted(exported) == ["clean", "dropped", "full", "review"]
    assert (tmp_path / "exports" / "clean.parquet").exists()
```

- [ ] **Step 2: Write failing update tests**

```python
def test_result_update_applies_columns_by_image_id(tmp_path: Path) -> None:
    result = BasicCleaner(["decode"]).run_sync(_dataset(tmp_path), run_id="run-1")

    updated = result.update(
        pd.DataFrame(
            {
                "image_id": ["ok"],
                "manual_action": ["drop"],
                "manual_reason": ["user rejected"],
            }
        )
    )

    full = updated.export(
        "full",
        tmp_path / "full.parquet",
        include_columns=["manual_action", "manual_reason"],
    ).to_frame()
    assert full.loc[full["image_id"] == "ok", "manual_action"].iloc[0] == "drop"
```

- [ ] **Step 3: Run tests to verify failure**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_export_all.py tests/unit/cleaning/test_result_update.py -q`

Expected: FAIL until export/update contracts are implemented.

- [ ] **Step 4: Implement Dataset view builder**

Rules:
- Default output columns exactly match input Dataset columns.
- `include_columns` appends selected evaluation/parameter columns.
- `full/clean/review/dropped` are Dataset views.
- `parameter/evaluation` remain available through `export_table()` only.
- `export("ALL")` writes `full.parquet`、`clean.parquet`、`review.parquet`、`dropped.parquet` to a directory.

- [ ] **Step 5: Implement update/apply**

Rules:
- `frame` must contain join key.
- Unknown ids raise `KeyError`.
- Persist updated evaluation table in the active store.
- `apply()` is an alias of `update()` in first version.

- [ ] **Step 6: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_export_all.py tests/unit/cleaning/test_result_update.py tests/integration/cleaning/test_basic_cleaner_export.py -q`

Expected: PASS after integration tests are updated for new export column contract.

---

### Task 8: ParameterComputer `before_run_check()`

**Files:**
- Modify: `src/image_gallery/operators/computers/base.py`
- Modify: `src/image_gallery/cleaning/execution.py`
- Modify: `src/image_gallery/operators/computers/semantic.py`
- Test: `tests/unit/operators/test_computer_checks.py`

**Interfaces:**
- Produces: `ParameterComputer.before_run_check(config: dict[str, object], storage: str = "temporary") -> list[ComputerCheckMessage]`
- Produces: `ComputerCheckMessage(level: Literal["warning", "error"], message: str, computer_name: str)`

- [ ] **Step 1: Write failing tests**

```python
from image_gallery.cleaning import BasicCleaner


def test_compile_reports_semantic_dependency_warning_without_running() -> None:
    diagnostics = BasicCleaner(["semantic_duplicate"]).compile().dry_run()

    messages = [*diagnostics.warnings, *diagnostics.errors]
    assert any("semantic" in message.lower() for message in messages)


def test_semantic_duplicate_rejects_memory_storage() -> None:
    diagnostics = BasicCleaner(["semantic_duplicate"]).compile().dry_run(run_options={"storage": "memory"})

    assert any("memory" in message.lower() for message in diagnostics.errors)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/python -m pytest tests/unit/operators/test_computer_checks.py -q`

Expected: FAIL because computer checks are not surfaced.

- [ ] **Step 3: Add check model and default hook**

```python
@dataclass(frozen=True)
class ComputerCheckMessage:
    """参数计算单元运行前检查消息。"""

    computer_name: str
    level: Literal["warning", "error"]
    message: str
```

Default `before_run_check()` returns an empty list.

- [ ] **Step 4: Wire dry-run checks**

Rules:
- Call checks for selected parameter computers.
- Add warnings/errors into `DryRunResult`.
- Do not read images, download models, or build indexes during checks.

- [ ] **Step 5: Implement semantic checks**

Rules:
- `storage="memory"` returns error for semantic operators.
- Missing `onnxruntime` or `huggingface_hub` returns warning or error before run.
- Explicit missing `model_path` returns error.
- Injected provider may skip optional dependency warning.

- [ ] **Step 6: Run tests**

Run: `.venv/bin/python -m pytest tests/unit/operators/test_computer_checks.py tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py -q`

Expected: PASS.

---

### Task 9: Documentation and example migration

**Files:**
- Modify: `README.md`
- Modify: `examples/README.md`
- Modify: `examples/stage4_basic_cleaner_quickstart.py`
- Create/Modify: `examples/cleaning_recipe.yaml`

**Interfaces:**
- Consumes all new public APIs from Tasks 1-8.

- [ ] **Step 1: Update quickstart to non-blocking run**

Use:

```python
run = BasicCleaner.from_recipe("examples/cleaning_recipe.yaml").run(dataset)
progress = run.get_progress()
result = run.wait()
exports = result.export("ALL", "outputs/datasets")
```

Also document sync shortcut:

```python
result = BasicCleaner(["decode", "blur"]).run_sync(dataset)
```

- [ ] **Step 2: Document recipe rules**

Include examples:

```yaml
- use: dimension
  drop:
    min_width: 256
    min_height: 256
  review:
    min_width: 512
    min_height: 512

- use: blur
  rules:
    drop: "[0, 0.3]"
    review: "(0.3, 0.6]"
```

- [ ] **Step 3: Document storage modes**

State:
- `temporary` is default.
- `memory` is for small, current-process runs only.
- `disk` is for long-lived resume/debug/audit.
- Semantic operators require filesystem-backed storage.

- [ ] **Step 4: Document export contract**

State:
- Result Dataset defaults to original input columns.
- Computed/evaluation columns require `include_columns`.
- `export_table()` is for full parameter/evaluation tables.

- [ ] **Step 5: Run example smoke test**

Run: `.venv/bin/python examples/stage4_basic_cleaner_quickstart.py`

Expected: script completes with short operator names and non-blocking or sync API.

---

## Acceptance Checks

- [ ] All builtin operators use short names as their primary `OperatorSpec.name`.
- [ ] Long names such as `quality.blur_check` are no longer accepted in primary APIs.
- [ ] `BasicCleaner.from_recipe("examples/cleaning_recipe.yaml")` works without notebook helper imports.
- [ ] Recipe supports absolute natural-unit rules for `dimension` / `megapixel` / `aspect_ratio`.
- [ ] Recipe supports relative interval rules for subjective quality operators.
- [ ] `run()` and `resume()` return `CleanerRun`; `run_sync()` and `resume_sync()` return `CleanerResult`.
- [ ] `CleanerRun.get_progress()` returns status, total, processed, percent and current node.
- [ ] `CleanerRun.stop()` requests cooperative stop and runtime can reach `stopped`.
- [ ] `storage` supports `memory | temporary | disk`; default is `temporary`.
- [ ] `run(output_dir=..., cache_root=..., storage=...)` has predictable path semantics and rejects misspelled options.
- [ ] `result.export("ALL", output_dir)` exports `full/clean/review/dropped` views and returns `dict[str, Dataset]`.
- [ ] Default `result.export("clean", path)` preserves input Dataset columns and storage.
- [ ] `include_columns` is required to include computed or evaluation columns.
- [ ] `result.update()` and `result.apply()` can update result columns by `image_id`.
- [ ] Semantic dependency/model/storage problems are visible before image processing starts.
- [ ] No `run_and_export` API is introduced.
- [ ] Duplicate keep strategy enhancements remain out of scope for this round.

## Suggested Validation Commands

```bash
.venv/bin/python -m pytest tests/unit/operators/test_builtin_specs.py tests/unit/cleaning/test_selection.py -q
.venv/bin/python -m pytest tests/unit/cleaning/test_rules.py tests/unit/cleaning/test_recipe.py -q
.venv/bin/python -m pytest tests/unit/cleaning/test_thresholds.py -q
.venv/bin/python -m pytest tests/unit/cleaning/test_run_store.py tests/unit/cleaning/test_run_handle.py -q
.venv/bin/python -m pytest tests/unit/cleaning/test_run_options.py -q
.venv/bin/python -m pytest tests/unit/cleaning/test_export_all.py tests/unit/cleaning/test_result_update.py -q
.venv/bin/python -m pytest tests/unit/operators/test_computer_checks.py -q
.venv/bin/python -m pytest tests/integration/cleaning -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m mypy src/image_gallery
```

## Deferred Follow-Ups

- Duplicate keep policy: `highest_resolution`、`best_quality`、`prefer_source`、多列排序保留策略。
- Complex `hybrid` run store: tables in memory, heavyweight artifacts on disk.
- Training/export node: YOLO、COCO、LabelImg、文件夹复制/软链接、train/val/test split。
- Interactive threshold calibration UI or notebook widget.
