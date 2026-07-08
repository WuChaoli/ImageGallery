# Cleaning Planner/Scheduler Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `BasicCleaner` into a compiled cleaning plan flow with explicit parameter dependency planning, scheduled parameter computation, and isolated operator evaluation.

**Architecture:** `BasicCleaner` remains the public facade. `CleaningRunPlanner` compiles operator configs into a `CompiledCleaningPlan`; `ParameterScheduler` executes the parameter steps; `OperatorEvaluator` evaluates logical operators. Parameter execution order is determined by a computer dependency DAG, while `ExecutionMode` only selects execution behavior.

**Tech Stack:** Python 3.10, pandas, pytest, ruff, mypy, ImageGallery `Dataset`, `BasicCleaner`, `OperatorRegistry`, `ParameterComputer`.

## Global Constraints

- User-facing operator config format remains `list[{operator_name: config}]`.
- Internal compatibility with `ComputeStage.stage` is not required; replace it with `ExecutionMode.execution_mode`.
- Do not implement CLIP, YOLO, near duplicate, model inference, chunked image batches, checkpoint/resume, DAG runtime concurrency, or SQLite-backed parameter storage in this plan.
- `rerun()` remains evaluation-only.
- `PER_IMAGE` keeps the current full shared `ImageBatch` behavior.
- Run-time tables remain in-memory DataFrames and are written at completion as Parquet/JSON.
- Use `.venv/bin/python` for all Python commands.
- Keep changes scoped to cleaning/operator execution; do not edit notebook files in this refactor.

---

## File Structure

Create:

- `src/image_gallery/cleaning/planner.py`
  - Owns `ResolvedOperatorRun`, `ParameterExecutionStep`, `ParameterExecutionPlan`, `CompiledCleaningPlan`, and `CleaningRunPlanner`.
  - Builds a computer DAG from operator final parameters and registry parameter producers.
  - Produces topologically sorted computer-level execution steps.

- `src/image_gallery/cleaning/scheduler.py`
  - Owns `ParameterScheduler` and `ParameterScheduleResult`.
  - Builds shared `ImageBatch`.
  - Executes parameter computers from a compiled `ParameterExecutionPlan`.
  - Merges parameter updates, manifest, artifacts, and relation paths.

- `src/image_gallery/cleaning/evaluator.py`
  - Owns `OperatorEvaluator`.
  - Applies `OperatorSpec.evaluate()` and updates evaluation tables/operator outputs.
  - Produces `OperatorRunState`.

Modify:

- `src/image_gallery/operators/computers/base.py`
  - Rename `ComputeStage` to `ExecutionMode`.
  - Rename `ParameterComputer.stage` to `ParameterComputer.execution_mode`.

- `src/image_gallery/operators/computers/*.py`
  - Update all built-in computers to use `execution_mode`.
  - Update manifest field from `"stage"` to `"execution_mode"`.

- `src/image_gallery/operators/registry.py`
  - Maintain a `parameter_name -> computer_name` producer index.
  - Reject duplicate parameter producers at registration time.
  - Provide lookup helpers for planner.

- `src/image_gallery/cleaning/cleaner.py`
  - Add abstract `compile()` and `plan()` methods.

- `src/image_gallery/cleaning/basic.py`
  - Remove embedded planning/scheduling/evaluation responsibilities.
  - Cache `_compiled_plan`.
  - Implement `compile()` and `plan()`.
  - Delegate parameter computation to `ParameterScheduler`.
  - Delegate operator evaluation to `OperatorEvaluator`.

Tests to create or modify:

- `tests/unit/operators/test_registry.py`
- `tests/unit/operators/test_parameter_computer_contract.py`
- `tests/unit/operators/test_metadata_computer.py`
- `tests/unit/operators/test_quality_computer.py`
- `tests/unit/operators/test_hash_computer.py`
- `tests/unit/operators/test_duplicate_computer.py`
- `tests/unit/operators/test_derived_computer.py`
- `tests/unit/cleaning/test_planner.py`
- `tests/unit/cleaning/test_scheduler.py`
- `tests/unit/cleaning/test_evaluator.py`
- `tests/unit/cleaning/test_basic_cleaner.py`
- `tests/integration/cleaning/test_basic_cleaner_builtin_run.py`

---

### Task 1: Introduce ExecutionMode and Registry Producer Index

**Files:**
- Modify: `src/image_gallery/operators/computers/base.py`
- Modify: `src/image_gallery/operators/computers/metadata.py`
- Modify: `src/image_gallery/operators/computers/quality.py`
- Modify: `src/image_gallery/operators/computers/hash.py`
- Modify: `src/image_gallery/operators/computers/derived.py`
- Modify: `src/image_gallery/operators/computers/duplicate.py`
- Modify: `src/image_gallery/operators/registry.py`
- Modify: `tests/unit/operators/test_registry.py`
- Modify: `tests/unit/operators/test_parameter_computer_contract.py`
- Modify: existing computer tests under `tests/unit/operators/`

**Interfaces:**
- Consumes: Current `ParameterComputer` subclasses and `OperatorRegistry`.
- Produces:
  - `ExecutionMode` enum with values `PER_IMAGE`, `TABLE`, `DATASET_AGGREGATE`.
  - `ParameterComputer.execution_mode: ExecutionMode`.
  - `OperatorRegistry.get_parameter_producer(parameter_name: str) -> ParameterComputer`.
  - `OperatorRegistry.list_parameter_computers() -> list[ParameterComputer]`.

- [ ] **Step 1: Write failing registry tests for ExecutionMode and duplicate producers**

Replace the `ComputeStage` imports/usages in `tests/unit/operators/test_registry.py` test doubles with:

```python
from image_gallery.operators.computers.base import (
    ExecutionMode,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)


class DemoComputer(ParameterComputer):
    name = "demo_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"demo_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(
            parameter_updates=pd.DataFrame({"image_id": request.parameter_table["image_id"], "demo_score": [1.0]}),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={},
        )


class DuplicateProducerComputer(ParameterComputer):
    name = "duplicate_producer_computer"
    execution_mode = ExecutionMode.TABLE
    produced_parameters = frozenset({"demo_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(
            parameter_updates=pd.DataFrame({"image_id": request.parameter_table["image_id"], "demo_score": [2.0]}),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={},
        )
```

Add these tests:

```python
def test_registry_indexes_parameter_producers() -> None:
    registry = OperatorRegistry()
    computer = DemoComputer()

    registry.register_parameter_computer(computer)

    assert registry.get_parameter_producer("demo_score") is computer
    assert registry.list_parameter_computers() == [computer]


def test_registry_rejects_duplicate_parameter_producers() -> None:
    registry = OperatorRegistry()
    registry.register_parameter_computer(DemoComputer())

    with pytest.raises(ValueError, match="parameter already has producer"):
        registry.register_parameter_computer(DuplicateProducerComputer())
```

- [ ] **Step 2: Run registry test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators/test_registry.py -q
```

Expected: FAIL because `ExecutionMode`, `get_parameter_producer`, `list_parameter_computers`, and duplicate producer checks are not implemented.

- [ ] **Step 3: Replace ComputeStage with ExecutionMode in base contract**

Modify `src/image_gallery/operators/computers/base.py`:

```python
class ExecutionMode(str, Enum):
    """参数计算执行模式。"""

    PER_IMAGE = "per_image"
    TABLE = "table"
    DATASET_AGGREGATE = "dataset_aggregate"
```

Update `ParameterComputer`:

```python
class ParameterComputer(ABC):
    """参数计算单元基类。"""

    name: str
    execution_mode: ExecutionMode
    produced_parameters: frozenset[str]
    required_parameters: frozenset[str] = frozenset()

    @abstractmethod
    def compute(self, request: ParameterRequest) -> ParameterResult:
        """按请求批量生产参数列。"""
```

Remove `ComputeStage`.

- [ ] **Step 4: Update built-in computers**

Use these replacements:

```python
# metadata.py, quality.py, hash.py
execution_mode = ExecutionMode.PER_IMAGE
```

```python
# derived.py
execution_mode = ExecutionMode.TABLE
```

```python
# duplicate.py
execution_mode = ExecutionMode.DATASET_AGGREGATE
```

Update imports from `ComputeStage` to `ExecutionMode`.

Update manifest entries in all computers from:

```python
"stage": self.stage.value,
```

to:

```python
"execution_mode": self.execution_mode.value,
```

- [ ] **Step 5: Implement registry producer index**

Modify `src/image_gallery/operators/registry.py`:

```python
class OperatorRegistry:
    """逻辑算子和参数计算单元注册表。"""

    def __init__(self) -> None:
        self._operators: dict[str, OperatorSpec] = {}
        self._parameter_computers: dict[str, ParameterComputer] = {}
        self._parameter_producers: dict[str, str] = {}
```

Update `register_parameter_computer`:

```python
def register_parameter_computer(self, computer: ParameterComputer) -> None:
    """注册参数计算单元，并索引参数生产者。"""
    for parameter_name in computer.produced_parameters:
        existing_computer = self._parameter_producers.get(parameter_name)
        if existing_computer is not None and existing_computer != computer.name:
            raise ValueError(
                f"parameter already has producer: {parameter_name} "
                f"({existing_computer}, {computer.name})"
            )
    self._parameter_computers[computer.name] = computer
    for parameter_name in computer.produced_parameters:
        self._parameter_producers[parameter_name] = computer.name
```

Add:

```python
def list_parameter_computers(self) -> list[ParameterComputer]:
    """返回注册顺序下的参数计算单元。"""
    return list(self._parameter_computers.values())

def get_parameter_producer(self, parameter_name: str) -> ParameterComputer:
    """返回生产指定参数的计算单元。"""
    try:
        computer_name = self._parameter_producers[parameter_name]
    except KeyError as exc:
        raise UnknownOperatorError(f"missing parameter producer: {parameter_name}") from exc
    return self.get_parameter_computer(computer_name)
```

Keep `find_computers_for_parameters()` temporarily for compatibility with current `BasicCleaner`; update it to use `execution_mode`-compatible computers but do not remove it yet.

Do not run cleaning tests in Task 1. Until Task 5 migrates `BasicCleaner`, cleaning modules may still contain old internal references while operator-only tests validate the new computer contract.

- [ ] **Step 6: Update tests for manifest field**

In `tests/unit/operators/test_parameter_computer_contract.py`, replace `stage` with `execution_mode`:

```python
from image_gallery.operators.computers.base import (
    ExecutionMode,
    ImageBatch,
    ImageBatchItem,
    ParameterComputer,
    ParameterRequest,
    ParameterResult,
)


class DemoComputer(ParameterComputer):
    name = "demo_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"demo_score"})
```

Update manifest:

```python
"execution_mode": self.execution_mode.value,
```

In built-in computer tests, replace assertions expecting `"stage"` with `"execution_mode"` and expected values with `per_image`, `table`, or `dataset_aggregate`.

- [ ] **Step 7: Run operator tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

```bash
git add src/image_gallery/operators tests/unit/operators
git commit -m "refactor: add execution modes to parameter computers"
```

---

### Task 2: Add CleaningRunPlanner and Compiled Plan Models

**Files:**
- Create: `src/image_gallery/cleaning/planner.py`
- Modify: `tests/unit/cleaning/test_planner.py`
- Modify: `src/image_gallery/cleaning/__init__.py` only if exports are needed by tests or public use

**Interfaces:**
- Consumes:
  - `ParsedOperatorConfig`
  - `merge_default_config(parsed_config, default_config)`
  - `OperatorRegistry.get_operator(operator_name)`
  - `OperatorRegistry.get_parameter_producer(parameter_name)`
- Produces:
  - `ResolvedOperatorRun`
  - `ParameterExecutionStep`
  - `ParameterExecutionPlan`
  - `CompiledCleaningPlan`
  - `CleaningRunPlanner.compile(parsed_configs: list[ParsedOperatorConfig]) -> CompiledCleaningPlan`
  - `ParameterExecutionPlan.to_frame() -> pd.DataFrame`

- [ ] **Step 1: Write failing planner tests**

Create `tests/unit/cleaning/test_planner.py`:

```python
import pandas as pd
import pytest

from image_gallery.cleaning.config import parse_operator_configs
from image_gallery.cleaning.planner import CleaningRunPlanner
from image_gallery.cleaning.errors import UnknownOperatorError
from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer, ParameterRequest, ParameterResult
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


class FeatureComputer(ParameterComputer):
    name = "feature_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"feature_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(pd.DataFrame(), {}, {}, {})


class AggregateComputer(ParameterComputer):
    name = "aggregate_computer"
    execution_mode = ExecutionMode.DATASET_AGGREGATE
    produced_parameters = frozenset({"group_id", "group_count"})
    required_parameters = frozenset({"feature_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(pd.DataFrame(), {}, {}, {})


class OtherComputer(ParameterComputer):
    name = "other_computer"
    execution_mode = ExecutionMode.TABLE
    produced_parameters = frozenset({"other_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(pd.DataFrame(), {}, {}, {})


def _evaluate(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame({"image_id": parameter_table["image_id"], "demo_action": "keep", "demo_reason": ""})


def _registry() -> OperatorRegistry:
    registry = OperatorRegistry()
    registry.register_parameter_computer(FeatureComputer())
    registry.register_parameter_computer(AggregateComputer())
    registry.register_parameter_computer(OtherComputer())
    registry.register_operator(
        OperatorSpec(
            name="duplicate.demo_check",
            category="duplicate",
            required_parameters=["group_id", "group_count"],
            evaluation_columns=["demo_action", "demo_reason"],
            default_config={"action": "drop"},
            action_column="demo_action",
            reason_column="demo_reason",
            evaluator=_evaluate,
        )
    )
    registry.register_operator(
        OperatorSpec(
            name="quality.other_check",
            category="quality",
            required_parameters=["other_score"],
            evaluation_columns=["demo_action", "demo_reason"],
            default_config={},
            action_column="demo_action",
            reason_column="demo_reason",
            evaluator=_evaluate,
        )
    )
    return registry


def test_planner_expands_parameter_dependencies_in_topological_order() -> None:
    parsed = parse_operator_configs([{"duplicate.demo_check": {}}])

    plan = CleaningRunPlanner(_registry()).compile(parsed)

    assert [step.computer_name for step in plan.parameter_plan.steps] == [
        "feature_computer",
        "aggregate_computer",
    ]
    assert plan.parameter_plan.steps[0].requested_parameters == frozenset({"feature_score"})
    assert plan.parameter_plan.steps[1].requested_parameters == frozenset({"group_count", "group_id"})
    assert plan.parameter_plan.steps[1].upstream_computer_names == ("feature_computer",)
    assert [run.spec.name for run in plan.resolved_operator_runs] == ["duplicate.demo_check"]


def test_planner_merges_requested_parameters_per_computer() -> None:
    parsed = parse_operator_configs([{"duplicate.demo_check": {}}, {"quality.other_check": {}}])

    plan = CleaningRunPlanner(_registry()).compile(parsed)

    rows_by_name = {
        row["computer_name"]: row
        for row in plan.parameter_plan.to_frame().to_dict(orient="records")
    }
    names = [step.computer_name for step in plan.parameter_plan.steps]
    assert set(names) == {"feature_computer", "aggregate_computer", "other_computer"}
    assert names.index("feature_computer") < names.index("aggregate_computer")
    assert rows_by_name["aggregate_computer"]["requested_parameters"] == "group_count,group_id"
    assert rows_by_name["other_computer"]["requested_parameters"] == "other_score"


def test_planner_rejects_missing_parameter_producer() -> None:
    registry = OperatorRegistry()
    registry.register_operator(
        OperatorSpec(
            name="quality.missing_check",
            category="quality",
            required_parameters=["missing_score"],
            evaluation_columns=["demo_action", "demo_reason"],
            default_config={},
            action_column="demo_action",
            reason_column="demo_reason",
            evaluator=_evaluate,
        )
    )
    parsed = parse_operator_configs([{"quality.missing_check": {}}])

    with pytest.raises(UnknownOperatorError, match="missing parameter producer"):
        CleaningRunPlanner(registry).compile(parsed)


def test_planner_rejects_dependency_cycle() -> None:
    class AComputer(ParameterComputer):
        name = "a_computer"
        execution_mode = ExecutionMode.TABLE
        produced_parameters = frozenset({"a"})
        required_parameters = frozenset({"b"})

        def compute(self, request: ParameterRequest) -> ParameterResult:
            return ParameterResult(pd.DataFrame(), {}, {}, {})

    class BComputer(ParameterComputer):
        name = "b_computer"
        execution_mode = ExecutionMode.TABLE
        produced_parameters = frozenset({"b"})
        required_parameters = frozenset({"a"})

        def compute(self, request: ParameterRequest) -> ParameterResult:
            return ParameterResult(pd.DataFrame(), {}, {}, {})

    registry = OperatorRegistry()
    registry.register_parameter_computer(AComputer())
    registry.register_parameter_computer(BComputer())
    registry.register_operator(
        OperatorSpec(
            name="quality.cycle_check",
            category="quality",
            required_parameters=["a"],
            evaluation_columns=["demo_action", "demo_reason"],
            default_config={},
            action_column="demo_action",
            reason_column="demo_reason",
            evaluator=_evaluate,
        )
    )

    with pytest.raises(ValueError, match="parameter dependency cycle"):
        CleaningRunPlanner(registry).compile(parse_operator_configs([{"quality.cycle_check": {}}]))
```

- [ ] **Step 2: Run planner tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_planner.py -q
```

Expected: FAIL because `image_gallery.cleaning.planner` does not exist.

- [ ] **Step 3: Implement planner models**

Create `src/image_gallery/cleaning/planner.py` with:

```python
from dataclasses import dataclass

import pandas as pd

from image_gallery.cleaning.config import ParsedOperatorConfig, merge_default_config
from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


@dataclass(frozen=True)
class ResolvedOperatorRun:
    """一次运行中已绑定 spec 和配置的逻辑算子。"""

    parsed_config: ParsedOperatorConfig
    spec: OperatorSpec
    merged_config: dict[str, object]


@dataclass(frozen=True)
class ParameterExecutionStep:
    """一个已拓扑排序的参数计算步骤。"""

    computer_name: str
    requested_parameters: frozenset[str]
    required_parameters: frozenset[str]
    produced_parameters: frozenset[str]
    execution_mode: ExecutionMode
    upstream_computer_names: tuple[str, ...]


@dataclass(frozen=True)
class ParameterExecutionPlan:
    """参数计算执行计划。"""

    steps: tuple[ParameterExecutionStep, ...]

    def to_frame(self) -> pd.DataFrame:
        """把执行计划转为 Notebook 友好的 DataFrame。"""
        rows = []
        for index, step in enumerate(self.steps):
            rows.append(
                {
                    "step_index": index,
                    "computer_name": step.computer_name,
                    "execution_mode": step.execution_mode.value,
                    "requested_parameters": ",".join(sorted(step.requested_parameters)),
                    "required_parameters": ",".join(sorted(step.required_parameters)),
                    "produced_parameters": ",".join(sorted(step.produced_parameters)),
                    "upstream_computers": ",".join(step.upstream_computer_names),
                }
            )
        return pd.DataFrame(
            rows,
            columns=[
                "step_index",
                "computer_name",
                "execution_mode",
                "requested_parameters",
                "required_parameters",
                "produced_parameters",
                "upstream_computers",
            ],
        )


@dataclass(frozen=True)
class CompiledCleaningPlan:
    """编译后的 Cleaner 执行计划。"""

    resolved_operator_runs: tuple[ResolvedOperatorRun, ...]
    parameter_plan: ParameterExecutionPlan
    operator_config_hashes: dict[str, str]
```

- [ ] **Step 4: Implement CleaningRunPlanner**

Append to `src/image_gallery/cleaning/planner.py`:

```python
class CleaningRunPlanner:
    """把逻辑算子配置编译为参数计算计划。"""

    def __init__(self, registry: OperatorRegistry) -> None:
        self._registry = registry

    def compile(self, parsed_configs: list[ParsedOperatorConfig]) -> CompiledCleaningPlan:
        """编译清洗计划，不读取 dataset，不产生运行产物。"""
        resolved_runs = tuple(self._resolve_operator_configs(parsed_configs))
        target_parameters = {parameter for run in resolved_runs for parameter in run.spec.required_parameters}
        parameter_plan = self._build_parameter_plan(target_parameters)
        return CompiledCleaningPlan(
            resolved_operator_runs=resolved_runs,
            parameter_plan=parameter_plan,
            operator_config_hashes={run.spec.name: run.parsed_config.config_hash for run in resolved_runs},
        )

    def _resolve_operator_configs(self, parsed_configs: list[ParsedOperatorConfig]) -> list[ResolvedOperatorRun]:
        resolved: list[ResolvedOperatorRun] = []
        for parsed_config in parsed_configs:
            spec = self._registry.get_operator(parsed_config.operator_name)
            merged = merge_default_config(parsed_config, spec.default_config)
            resolved.append(ResolvedOperatorRun(parsed_config=merged, spec=spec, merged_config=merged.config))
        return resolved

    def _build_parameter_plan(self, target_parameters: set[str]) -> ParameterExecutionPlan:
        requested_by_computer: dict[str, set[str]] = {}
        upstream_by_computer: dict[str, set[str]] = {}
        computer_by_name = {computer.name: computer for computer in self._registry.list_parameter_computers()}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit_parameter(parameter_name: str) -> str:
            computer = self._registry.get_parameter_producer(parameter_name)
            requested_by_computer.setdefault(computer.name, set()).add(parameter_name)
            visit_computer(computer.name)
            return computer.name

        def visit_computer(computer_name: str) -> None:
            if computer_name in visiting:
                cycle = " -> ".join([*sorted(visiting), computer_name])
                raise ValueError(f"parameter dependency cycle: {cycle}")
            if computer_name in visited:
                return
            visiting.add(computer_name)
            computer = computer_by_name[computer_name]
            upstream_names: set[str] = set()
            for required_parameter in computer.required_parameters:
                upstream_name = visit_parameter(required_parameter)
                if upstream_name != computer_name:
                    upstream_names.add(upstream_name)
            upstream_by_computer[computer_name] = upstream_names
            visiting.remove(computer_name)
            visited.add(computer_name)

        for parameter_name in sorted(target_parameters):
            visit_parameter(parameter_name)

        ordered_names = self._topological_order(upstream_by_computer, computer_by_name)
        steps = []
        for computer_name in ordered_names:
            computer = computer_by_name[computer_name]
            steps.append(
                ParameterExecutionStep(
                    computer_name=computer.name,
                    requested_parameters=frozenset(requested_by_computer.get(computer.name, set())),
                    required_parameters=frozenset(computer.required_parameters),
                    produced_parameters=frozenset(computer.produced_parameters),
                    execution_mode=computer.execution_mode,
                    upstream_computer_names=tuple(sorted(upstream_by_computer.get(computer.name, set()))),
                )
            )
        return ParameterExecutionPlan(steps=tuple(steps))

    def _topological_order(
        self,
        upstream_by_computer: dict[str, set[str]],
        computer_by_name: dict[str, ParameterComputer],
    ) -> list[str]:
        mode_order = {
            ExecutionMode.PER_IMAGE: 0,
            ExecutionMode.TABLE: 1,
            ExecutionMode.DATASET_AGGREGATE: 2,
        }
        remaining = {name: set(upstreams) for name, upstreams in upstream_by_computer.items()}
        ordered: list[str] = []
        while remaining:
            ready = sorted(
                (name for name, upstreams in remaining.items() if not upstreams),
                key=lambda name: (mode_order[computer_by_name[name].execution_mode], name),
            )
            if not ready:
                cycle = " -> ".join(sorted(remaining))
                raise ValueError(f"parameter dependency cycle: {cycle}")
            for name in ready:
                ordered.append(name)
                remaining.pop(name)
            for upstreams in remaining.values():
                upstreams.difference_update(ready)
        return ordered
```

- [ ] **Step 5: Run planner tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_planner.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/image_gallery/cleaning/planner.py tests/unit/cleaning/test_planner.py
git commit -m "feat: compile cleaning parameter execution plans"
```

---

### Task 3: Extract ParameterScheduler

**Files:**
- Create: `src/image_gallery/cleaning/scheduler.py`
- Modify: `tests/unit/cleaning/test_scheduler.py`
- Modify: `src/image_gallery/cleaning/basic.py` only if helper extraction is needed by tests; main integration happens in Task 5

**Interfaces:**
- Consumes:
  - `ParameterExecutionPlan`
  - `ParameterExecutionStep`
  - `CleanerRunContext`
  - `CleaningTables`
  - `OperatorRegistry`
  - `update_parameter_columns()`
  - `write_relation_tables()`
- Produces:
  - `ParameterScheduleResult(tables: CleaningTables, artifact_paths: dict[str, str], relation_paths: dict[str, str])`
  - `ParameterScheduler.run(plan, context, tables) -> ParameterScheduleResult`

- [ ] **Step 1: Write failing scheduler tests**

Create `tests/unit/cleaning/test_scheduler.py`:

```python
from io import BytesIO
from pathlib import Path

import pandas as pd
from PIL import Image

from image_gallery.cleaning.config import parse_operator_configs
from image_gallery.cleaning.context import create_run_context
from image_gallery.cleaning.planner import CleaningRunPlanner
from image_gallery.cleaning.scheduler import ParameterScheduler
from image_gallery.cleaning.tables import CleaningTables, initialize_evaluation_table, initialize_parameter_table
from image_gallery.dataset import Dataset
from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer, ParameterRequest, ParameterResult
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


class CountingImageComputer(ParameterComputer):
    name = "counting_image_computer"
    execution_mode = ExecutionMode.PER_IMAGE
    produced_parameters = frozenset({"image_score"})

    def __init__(self) -> None:
        self.calls = 0

    def compute(self, request: ParameterRequest) -> ParameterResult:
        self.calls += 1
        assert request.image_batch is not None
        return ParameterResult(
            parameter_updates=pd.DataFrame(
                {
                    "image_id": [item.image_id for item in request.image_batch.items],
                    "image_score": [1.0 for _ in request.image_batch.items],
                }
            ),
            relation_updates={},
            artifact_refs={"counting_image_computer": str(request.artifacts_dir / "image")},
            parameter_manifest={
                "image_score": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                }
            },
        )


class TableComputer(ParameterComputer):
    name = "table_computer"
    execution_mode = ExecutionMode.TABLE
    produced_parameters = frozenset({"table_score"})
    required_parameters = frozenset({"image_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        assert request.image_batch is None
        return ParameterResult(
            parameter_updates=pd.DataFrame(
                {
                    "image_id": request.parameter_table["image_id"],
                    "table_score": request.parameter_table["image_score"] + 1.0,
                }
            ),
            relation_updates={},
            artifact_refs={},
            parameter_manifest={
                "table_score": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                    "depends_on": ["image_score"],
                }
            },
        )


class AggregateComputer(ParameterComputer):
    name = "aggregate_computer"
    execution_mode = ExecutionMode.DATASET_AGGREGATE
    produced_parameters = frozenset({"group_id"})
    required_parameters = frozenset({"table_score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        assert request.image_batch is None
        return ParameterResult(
            parameter_updates=pd.DataFrame({"image_id": request.parameter_table["image_id"], "group_id": ["g1"]}),
            relation_updates={
                "demo_pairs": pd.DataFrame(
                    {
                        "relation_type": ["demo"],
                        "source_image_id": ["img-1"],
                        "target_image_id": ["img-1"],
                        "score": [1.0],
                        "group_id": ["g1"],
                        "parameter_name": ["group_id"],
                        "computer_name": [self.name],
                        "artifact_ref": [""],
                        "created_at": ["2026-07-08T00:00:00Z"],
                    }
                )
            },
            artifact_refs={},
            parameter_manifest={
                "group_id": {
                    "computer": self.name,
                    "execution_mode": self.execution_mode.value,
                    "config_hash": request.config_hash,
                    "depends_on": ["table_score"],
                }
            },
        )


class CountingReadDataset(Dataset):
    def __init__(self, dataset_path: str, image_bytes: bytes) -> None:
        super().__init__(dataset_path=dataset_path)
        self.image_bytes = image_bytes
        self.read_calls: list[str] = []

    def read_image_bytes(self, image_uri: str) -> bytes:
        self.read_calls.append(image_uri)
        return self.image_bytes


def _evaluate(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame({"image_id": parameter_table["image_id"], "demo_action": "keep", "demo_reason": ""})


def _registry(image_computer: CountingImageComputer) -> OperatorRegistry:
    registry = OperatorRegistry()
    registry.register_parameter_computer(image_computer)
    registry.register_parameter_computer(TableComputer())
    registry.register_parameter_computer(AggregateComputer())
    registry.register_operator(
        OperatorSpec(
            name="demo.aggregate_check",
            category="demo",
            required_parameters=["group_id"],
            evaluation_columns=["demo_action", "demo_reason"],
            default_config={},
            action_column="demo_action",
            reason_column="demo_reason",
            evaluator=_evaluate,
        )
    )
    return registry


def _dataset(tmp_path: Path) -> CountingReadDataset:
    image_buffer = BytesIO()
    Image.new("RGB", (2, 2), color=(255, 0, 0)).save(image_buffer, format="PNG")
    image_bytes = image_buffer.getvalue()
    raw_path = tmp_path / "raw.parquet"
    pd.DataFrame({"image_id": ["img-1"], "image_uri": [str(tmp_path / "img.png")]}).to_parquet(raw_path, index=False)
    return CountingReadDataset(str(raw_path), image_bytes)


def test_scheduler_executes_plan_and_merges_outputs(tmp_path: Path) -> None:
    image_computer = CountingImageComputer()
    registry = _registry(image_computer)
    dataset = _dataset(tmp_path)
    context = create_run_context(
        dataset,
        "basic",
        parse_operator_configs([{"demo.aggregate_check": {}}]),
        tmp_path / "cleaning",
    )
    parameter_table = initialize_parameter_table(dataset)
    tables = CleaningTables(
        parameter_table=parameter_table,
        evaluation_table=initialize_evaluation_table(parameter_table),
        operator_outputs={},
        parameter_manifest={},
    )
    plan = CleaningRunPlanner(registry).compile(parse_operator_configs([{"demo.aggregate_check": {}}]))

    result = ParameterScheduler(registry).run(plan.parameter_plan, context, tables)

    assert image_computer.calls == 1
    assert dataset.read_calls == [str(tmp_path / "img.png")]
    assert result.tables.parameter_table["group_id"].tolist() == ["g1"]
    assert set(result.tables.parameter_manifest) == {"image_score", "table_score", "group_id"}
    assert result.artifact_paths == {"counting_image_computer": str(context.paths.artifacts_dir / "image")}
    assert result.relation_paths["demo_pairs"].endswith("relations/demo_pairs.parquet")
```

- [ ] **Step 2: Run scheduler tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_scheduler.py -q
```

Expected: FAIL because `image_gallery.cleaning.scheduler` does not exist.

- [ ] **Step 3: Implement scheduler result and constructor**

Create `src/image_gallery/cleaning/scheduler.py`:

```python
from dataclasses import dataclass
from io import BytesIO

from PIL import Image

from image_gallery.cleaning.context import CleanerRunContext
from image_gallery.cleaning.planner import ParameterExecutionPlan, ParameterExecutionStep
from image_gallery.cleaning.tables import (
    CleaningTables,
    update_parameter_columns,
    write_relation_tables,
)
from image_gallery.operators.computers.base import (
    ExecutionMode,
    ImageBatch,
    ImageBatchItem,
    ParameterRequest,
)
from image_gallery.operators.registry import OperatorRegistry


@dataclass(frozen=True)
class ParameterScheduleResult:
    """参数计算调度结果。"""

    tables: CleaningTables
    artifact_paths: dict[str, str]
    relation_paths: dict[str, str]


class ParameterScheduler:
    """按已编译计划执行参数计算单元。"""

    def __init__(self, registry: OperatorRegistry) -> None:
        self._registry = registry
```

- [ ] **Step 4: Implement scheduler run loop**

Append to `ParameterScheduler`:

```python
def run(
    self,
    plan: ParameterExecutionPlan,
    context: CleanerRunContext,
    tables: CleaningTables,
) -> ParameterScheduleResult:
    """执行参数计划，并返回更新后的 tables 和产物路径。"""
    artifact_paths: dict[str, str] = {}
    relation_paths: dict[str, str] = {}
    image_batch = self._build_image_batch(context, tables) if self._requires_image_batch(plan) else None
    current_tables = tables

    for step in plan.steps:
        computer = self._registry.get_parameter_computer(step.computer_name)
        result = computer.compute(
            ParameterRequest(
                parameter_table=current_tables.parameter_table,
                requested_parameters=step.requested_parameters,
                config={},
                config_hash="default",
                artifacts_dir=context.paths.artifacts_dir,
                image_batch=image_batch if step.execution_mode == ExecutionMode.PER_IMAGE else None,
            )
        )
        self._require_requested_parameters(step, result.parameter_updates)
        current_tables = CleaningTables(
            parameter_table=update_parameter_columns(current_tables.parameter_table, result.parameter_updates),
            evaluation_table=current_tables.evaluation_table,
            operator_outputs=current_tables.operator_outputs,
            parameter_manifest={**current_tables.parameter_manifest, **result.parameter_manifest},
        )
        artifact_paths.update(result.artifact_refs)
        relation_paths.update(write_relation_tables(result.relation_updates, context.paths))

    return ParameterScheduleResult(tables=current_tables, artifact_paths=artifact_paths, relation_paths=relation_paths)
```

- [ ] **Step 5: Implement scheduler helpers**

Append:

```python
def _requires_image_batch(self, plan: ParameterExecutionPlan) -> bool:
    return any(step.execution_mode == ExecutionMode.PER_IMAGE for step in plan.steps)

def _build_image_batch(self, context: CleanerRunContext, tables: CleaningTables) -> ImageBatch:
    """统一读取和解码当前 parameter_table 中的图片。"""
    items: list[ImageBatchItem] = []
    for row in tables.parameter_table.to_dict(orient="records"):
        image_id = str(row["image_id"])
        image_uri = str(row["image_uri"])
        try:
            data = context.dataset.read_image_bytes(image_uri)
            with Image.open(BytesIO(data)) as opened:
                opened.load()
                image = opened.copy()
                image.format = opened.format
            items.append(ImageBatchItem(image_id, image_uri, row, data, image, None))
        except Exception as exc:
            items.append(ImageBatchItem(image_id, image_uri, row, None, None, str(exc)))
    return ImageBatch(items=items)

def _require_requested_parameters(self, step: ParameterExecutionStep, updates) -> None:
    missing_parameters = [
        parameter for parameter in sorted(step.requested_parameters) if parameter not in updates.columns
    ]
    if missing_parameters:
        raise ValueError(f"computer did not produce requested parameters: {step.computer_name} {missing_parameters}")
```

- [ ] **Step 6: Run scheduler tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_scheduler.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add src/image_gallery/cleaning/scheduler.py tests/unit/cleaning/test_scheduler.py
git commit -m "feat: add parameter scheduler"
```

---

### Task 4: Extract OperatorEvaluator

**Files:**
- Create: `src/image_gallery/cleaning/evaluator.py`
- Create: `tests/unit/cleaning/test_evaluator.py`

**Interfaces:**
- Consumes:
  - `ResolvedOperatorRun`
  - `CleaningTables`
  - `update_evaluation_columns()`
  - `update_operator_outputs()`
- Produces:
  - `OperatorEvaluator.evaluate(run: ResolvedOperatorRun, tables: CleaningTables) -> tuple[CleaningTables, OperatorRunState]`

- [ ] **Step 1: Write failing evaluator test**

Create `tests/unit/cleaning/test_evaluator.py`:

```python
import pandas as pd

from image_gallery.cleaning.config import parse_operator_configs
from image_gallery.cleaning.planner import CleaningRunPlanner
from image_gallery.cleaning.evaluator import OperatorEvaluator
from image_gallery.cleaning.tables import CleaningTables, initialize_evaluation_table
from image_gallery.operators.computers.base import ExecutionMode, ParameterComputer, ParameterRequest, ParameterResult
from image_gallery.operators.registry import OperatorRegistry
from image_gallery.operators.spec import OperatorSpec


class ScoreComputer(ParameterComputer):
    name = "score_computer"
    execution_mode = ExecutionMode.TABLE
    produced_parameters = frozenset({"score"})

    def compute(self, request: ParameterRequest) -> ParameterResult:
        return ParameterResult(pd.DataFrame(), {}, {}, {})


def _evaluate(parameter_table: pd.DataFrame, config: dict[str, object]) -> pd.DataFrame:
    threshold = float(config["threshold"])
    failed = parameter_table["score"] >= threshold
    return pd.DataFrame(
        {
            "image_id": parameter_table["image_id"],
            "score_action": failed.map(lambda value: "drop" if value else "keep"),
            "score_reason": failed.map(lambda value: "too high" if value else ""),
        }
    )


def test_operator_evaluator_updates_tables_and_state() -> None:
    registry = OperatorRegistry()
    registry.register_parameter_computer(ScoreComputer())
    registry.register_operator(
        OperatorSpec(
            name="quality.score_check",
            category="quality",
            required_parameters=["score"],
            evaluation_columns=["score_action", "score_reason"],
            default_config={"threshold": 0.5},
            action_column="score_action",
            reason_column="score_reason",
            evaluator=_evaluate,
        )
    )
    compiled = CleaningRunPlanner(registry).compile(parse_operator_configs([{"quality.score_check": {}}]))
    parameter_table = pd.DataFrame({"image_id": ["img-1"], "image_uri": ["a.jpg"], "score": [0.9]})
    tables = CleaningTables(
        parameter_table=parameter_table,
        evaluation_table=initialize_evaluation_table(parameter_table),
        operator_outputs={},
        parameter_manifest={},
    )

    updated_tables, state = OperatorEvaluator().evaluate(compiled.resolved_operator_runs[0], tables)

    assert updated_tables.evaluation_table["score_action"].tolist() == ["drop"]
    assert updated_tables.operator_outputs == {"quality.score_check": ["score_action", "score_reason"]}
    assert state.operator_name == "quality.score_check"
    assert state.parameter_columns == ["score"]
    assert state.evaluation_columns == ["score_action", "score_reason"]
    assert state.processed_count == 1
```

- [ ] **Step 2: Run evaluator test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_evaluator.py -q
```

Expected: FAIL because `image_gallery.cleaning.evaluator` does not exist.

- [ ] **Step 3: Implement OperatorEvaluator**

Create `src/image_gallery/cleaning/evaluator.py`:

```python
from image_gallery.cleaning.planner import ResolvedOperatorRun
from image_gallery.cleaning.state import OperatorRunState
from image_gallery.cleaning.tables import (
    CleaningTables,
    update_evaluation_columns,
    update_operator_outputs,
)


class OperatorEvaluator:
    """执行逻辑算子的评估阶段。"""

    def evaluate(
        self,
        run: ResolvedOperatorRun,
        tables: CleaningTables,
    ) -> tuple[CleaningTables, OperatorRunState]:
        """评估单个逻辑算子，并返回更新后的 tables 和状态。"""
        updates = run.spec.evaluate(tables.parameter_table, run.merged_config)
        operator_outputs = update_operator_outputs(
            tables.operator_outputs,
            run.spec.name,
            run.spec.evaluation_columns,
        )
        evaluation_table = update_evaluation_columns(
            tables.evaluation_table,
            updates,
            run.spec.evaluation_columns,
        )
        updated_tables = CleaningTables(
            parameter_table=tables.parameter_table,
            evaluation_table=evaluation_table,
            operator_outputs=operator_outputs,
            parameter_manifest=tables.parameter_manifest,
        )
        state = OperatorRunState(
            operator_name=run.spec.name,
            config_hash=run.parsed_config.config_hash,
            status="completed",
            parameter_columns=run.spec.required_parameters,
            evaluation_columns=run.spec.evaluation_columns,
            processed_count=len(tables.parameter_table),
            skipped_count=0,
            failed_count=0,
        )
        return updated_tables, state
```

- [ ] **Step 4: Run evaluator test**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_evaluator.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/image_gallery/cleaning/evaluator.py tests/unit/cleaning/test_evaluator.py
git commit -m "feat: add operator evaluator"
```

---

### Task 5: Integrate compile(), plan(), Planner, Scheduler, and Evaluator into BasicCleaner

**Files:**
- Modify: `src/image_gallery/cleaning/cleaner.py`
- Modify: `src/image_gallery/cleaning/basic.py`
- Modify: `tests/unit/cleaning/test_basic_cleaner.py`
- Modify: `tests/integration/cleaning/test_basic_cleaner_builtin_run.py`

**Interfaces:**
- Consumes:
  - `CleaningRunPlanner`
  - `CompiledCleaningPlan`
  - `ParameterScheduler`
  - `OperatorEvaluator`
- Produces:
  - `BasicCleaner.compile() -> BasicCleaner`
  - `BasicCleaner.plan() -> pd.DataFrame`
  - `BasicCleaner.run()` using compiled plan
  - `config()` invalidating `_compiled_plan`

- [ ] **Step 1: Add failing compile/plan tests**

Append to `tests/unit/cleaning/test_basic_cleaner.py`:

```python
def test_basic_cleaner_plan_auto_compiles_without_running_dataset(tmp_path: Path) -> None:
    computer = CountingComputer()
    cleaner = BasicCleaner(
        [
            {"quality.drop_check": {}},
            {"quality.review_check": {}},
        ],
        registry=_registry(computer),
    )

    frame = cleaner.plan()

    assert frame["computer_name"].tolist() == ["counting_computer"]
    assert frame["execution_mode"].tolist() == ["per_image"]
    assert frame["requested_parameters"].tolist() == ["demo_score"]
    assert computer.calls == []
    assert not (tmp_path / "cleaning").exists()


def test_basic_cleaner_compile_returns_self_and_run_uses_cached_plan(tmp_path: Path) -> None:
    computer = CountingComputer()
    cleaner = BasicCleaner([{"quality.drop_check": {}}], registry=_registry(computer))

    assert cleaner.compile() is cleaner
    cleaner.run(_dataset(tmp_path), output_dir=tmp_path / "cleaning")

    assert computer.calls == [({"demo_score"}, 2)]


def test_basic_cleaner_config_invalidates_compiled_plan(tmp_path: Path) -> None:
    computer = CountingComputer()
    cleaner = BasicCleaner([{"quality.drop_check": {}}], registry=_registry(computer))
    assert cleaner.plan()["requested_parameters"].tolist() == ["demo_score"]

    cleaner.config([{"quality.review_check": {}}])

    assert cleaner.plan()["computer_name"].tolist() == ["counting_computer"]
```

Update existing expected manifest in `test_basic_cleaner_runs_shared_parameter_computer_and_exposes_results`:

```python
assert pd.read_json(run_dir / "parameter_manifest.json", typ="series").to_dict()["demo_score"] == {
    "computer": "counting_computer",
    "config_hash": "default",
    "execution_mode": "per_image",
}
```

- [ ] **Step 2: Run BasicCleaner tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_basic_cleaner.py -q
```

Expected: FAIL because `compile()` and `plan()` are not implemented on `BasicCleaner`, and `BasicCleaner` still references old scheduling code.

- [ ] **Step 3: Add abstract methods to Cleaner**

Modify `src/image_gallery/cleaning/cleaner.py`:

```python
@abstractmethod
def compile(self) -> "Cleaner":
    """编译当前 Cleaner 配置，不读取 dataset，不写运行产物。"""

@abstractmethod
def plan(self) -> pd.DataFrame:
    """返回当前编译计划的可读表格。"""
```

Place these before `run()`.

- [ ] **Step 4: Refactor BasicCleaner imports and fields**

Modify `src/image_gallery/cleaning/basic.py` imports:

```python
from image_gallery.cleaning.evaluator import OperatorEvaluator
from image_gallery.cleaning.planner import CompiledCleaningPlan, CleaningRunPlanner, ResolvedOperatorRun
from image_gallery.cleaning.scheduler import ParameterScheduler
```

Remove local `ResolvedOperatorRun` dataclass and remove direct imports of `BytesIO`, `Image`, `ComputeStage`, `ImageBatch`, `ImageBatchItem`, `ParameterComputer`, `ParameterRequest`, and `ParameterResult` if no longer used.

Add field in `__init__`:

```python
self._compiled_plan: CompiledCleaningPlan | None = None
```

- [ ] **Step 5: Implement BasicCleaner compile() and plan()**

Add methods to `BasicCleaner`:

```python
def compile(self) -> "BasicCleaner":
    """编译当前算子配置并缓存执行计划。"""
    self._compiled_plan = CleaningRunPlanner(self._registry).compile(self._operator_configs)
    return self

def plan(self) -> pd.DataFrame:
    """返回当前参数计算计划。"""
    compiled_plan = self._require_compiled_plan()
    return compiled_plan.parameter_plan.to_frame()

def _require_compiled_plan(self) -> CompiledCleaningPlan:
    """返回已编译计划；不存在时自动编译。"""
    if self._compiled_plan is None:
        self.compile()
    if self._compiled_plan is None:
        raise CleanerStateError("BasicCleaner compile failed")
    return self._compiled_plan
```

- [ ] **Step 6: Replace run() parameter/evaluation internals**

In `run()`, replace:

```python
resolved_runs = self._resolve_operator_configs(self._operator_configs)
operator_states: list[OperatorRunState] = []

started_at = _utc_now()
artifact_paths, relation_paths = self._run_parameter_computers(resolved_runs)

for resolved_run in resolved_runs:
    operator_states.append(self._evaluate_operator(resolved_run))
```

with:

```python
compiled_plan = self._require_compiled_plan()
operator_states: list[OperatorRunState] = []

started_at = _utc_now()
schedule_result = ParameterScheduler(self._registry).run(compiled_plan.parameter_plan, context, tables)
tables = schedule_result.tables
self._tables = tables

evaluator = OperatorEvaluator()
for resolved_run in compiled_plan.resolved_operator_runs:
    tables, operator_state = evaluator.evaluate(resolved_run, tables)
    self._tables = tables
    operator_states.append(operator_state)

artifact_paths = schedule_result.artifact_paths
relation_paths = schedule_result.relation_paths
resolved_runs = list(compiled_plan.resolved_operator_runs)
```

Keep final action, state build, `write_tables()`, and state save behavior.

- [ ] **Step 7: Update config() invalidation and rerun resolution**

In `config()`, after replacing configs:

```python
self._compiled_plan = None
```

For stale state, replace direct `_resolve_operator_configs(parsed_configs)` with:

```python
resolved_runs = CleaningRunPlanner(self._registry).compile(parsed_configs).resolved_operator_runs
```

In `rerun()`, keep evaluation-only but use planner for resolving the passed configs:

```python
resolved_runs = CleaningRunPlanner(self._registry).compile(parsed_configs).resolved_operator_runs
evaluator = OperatorEvaluator()
_, tables, _ = self._require_run()
for resolved_run in resolved_runs:
    tables, operator_state = evaluator.evaluate(resolved_run, tables)
    self._tables = tables
    operator_states.append(operator_state)
```

After `_replace_operator_configs(parsed_configs)`, set:

```python
self._compiled_plan = None
```

- [ ] **Step 8: Remove old BasicCleaner private planning/scheduling/evaluation methods**

Delete these methods from `BasicCleaner` after the new flow compiles:

```python
_resolve_operator_configs()
_required_parameters()
_run_parameter_computers()
_run_parameter_computer()
_build_image_batch()
_evaluate_operator()
```

Keep `_require_run()`, `_build_state()`, `_replace_operator_configs()`, `_enabled_operator_configs_from_current()`, `_save_current_outputs()`, and `_utc_now()`.

Update `_enabled_operator_configs_from_current()`:

```python
resolved_runs = CleaningRunPlanner(self._registry).compile(self._operator_configs).resolved_operator_runs
return [{run.spec.name: run.merged_config} for run in resolved_runs]
```

- [ ] **Step 9: Run focused BasicCleaner tests**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning/test_basic_cleaner.py tests/integration/cleaning/test_basic_cleaner_builtin_run.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit Task 5**

```bash
git add src/image_gallery/cleaning/cleaner.py src/image_gallery/cleaning/basic.py tests/unit/cleaning/test_basic_cleaner.py tests/integration/cleaning/test_basic_cleaner_builtin_run.py
git commit -m "refactor: compile and execute basic cleaner plans"
```

---

### Task 6: Final Contract Cleanup and Regression Verification

**Files:**
- Modify: any remaining test or source file that imports `ComputeStage` or reads manifest `"stage"`
- Modify: docs only if implementation reveals a mismatch with the spec

**Interfaces:**
- Consumes: All previous tasks.
- Produces: Repository-wide consistency for `ExecutionMode`, `compile()`, `plan()`, planner, scheduler, and evaluator.

- [ ] **Step 1: Search for stale ComputeStage and stage manifest usage**

Run:

```bash
rg -n "ComputeStage|\\.stage\\b|\"stage\"|\\['stage'\\]" src tests docs/superpowers/specs/2026-07-08-cleaning-planner-scheduler-refactor-design.md
```

Expected: Only acceptable hits are spec text describing old `ComputeStage` migration. No source or test should import `ComputeStage` or assert manifest `"stage"`.

- [ ] **Step 2: If stale source/test hits exist, replace them**

Use these replacements:

```python
from image_gallery.operators.computers.base import ExecutionMode
```

```python
execution_mode = ExecutionMode.PER_IMAGE
execution_mode = ExecutionMode.TABLE
execution_mode = ExecutionMode.DATASET_AGGREGATE
```

Manifest keys should be:

```python
"execution_mode": self.execution_mode.value
```

- [ ] **Step 3: Run unit tests for cleaning and operators**

Run:

```bash
.venv/bin/python -m pytest tests/unit/operators tests/unit/cleaning -q
```

Expected: PASS.

- [ ] **Step 4: Run cleaning integration tests**

Run:

```bash
.venv/bin/python -m pytest tests/integration/cleaning -q
```

Expected: PASS or skip environment-dependent MinIO tests with explicit pytest skip messages.

- [ ] **Step 5: Run lint**

Run:

```bash
.venv/bin/python -m ruff check src/image_gallery tests/unit/operators tests/unit/cleaning tests/integration/cleaning
```

Expected: PASS.

- [ ] **Step 6: Run mypy**

Run:

```bash
.venv/bin/python -m mypy src/image_gallery
```

Expected: PASS. If mypy reports pre-existing unrelated failures outside touched files, record exact failures in the final implementation summary and do not fix unrelated code.

- [ ] **Step 7: Inspect final git diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: only files related to planner/scheduler/evaluator/basic cleaner/operator computer refactor are changed. Existing notebook/helper worktree changes may still be present from earlier work and should not be included in this refactor commits unless they were intentionally touched by a task.

- [ ] **Step 8: Commit final cleanup if needed**

If Step 1 or validation cleanup changed files after Task 5, commit them:

```bash
git add src/image_gallery tests/unit/operators tests/unit/cleaning tests/integration/cleaning docs/superpowers/specs/2026-07-08-cleaning-planner-scheduler-refactor-design.md
git commit -m "test: verify cleaning planner scheduler refactor"
```

If no files changed, do not create an empty commit.

---

## Self-Review Checklist

- Spec coverage:
  - `Cleaner.compile()` and `Cleaner.plan()` are covered by Task 5.
  - `ExecutionMode` replacement is covered by Task 1.
  - Registry parameter producer index and duplicate producer rejection are covered by Task 1.
  - Computer DAG and topological plan compilation are covered by Task 2.
  - Scheduler extraction and shared image batch behavior are covered by Task 3.
  - Evaluator extraction is covered by Task 4.
  - BasicCleaner facade integration is covered by Task 5.
  - Checkpoint/store remains a future extension and is not implemented.

- Placeholder scan:
  - No implementation step uses TBD/TODO/fill-in placeholders.
  - Each code-changing task includes concrete snippets and expected test commands.

- Type consistency:
  - The plan consistently uses `ExecutionMode`, `execution_mode`, `ParameterExecutionStep`, `ParameterExecutionPlan`, `CompiledCleaningPlan`, `CleaningRunPlanner`, `ParameterScheduler`, and `OperatorEvaluator`.
  - `compile()` returns `BasicCleaner`/`Cleaner`; `plan()` returns `pd.DataFrame`.
