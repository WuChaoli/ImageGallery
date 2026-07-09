# Cleaner Runtime StateGraph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the new Cleaner runtime lifecycle: `BasicCleaner` as builder, `CleanerExecution` as graph executor, and `CleanerResult` as the only result/export/preview surface.

**Architecture:** The implementation replaces the current one-shot `BasicCleaner.run()` internals with a stage-level `CleaningStateGraph`, SQLite-backed runtime state, run-internal artifact manifests, and system-cache-backed result files. Public code keeps a convenient `BasicCleaner(operator_configs).run(dataset)` shortcut, but the real lifecycle is `BasicCleaner(operator_configs).compile().run(dataset) -> CleanerResult`.

**Tech Stack:** Python 3.10, pandas, SQLite via stdlib `sqlite3`, pathlib/json/zipfile, existing `Dataset`, existing operator registry and `ParameterComputer` abstractions, pytest, ruff, mypy.

## Global Constraints

- Python package/API first; no service API, no Web UI, no distributed scheduler.
- Use `.venv/bin/python` for local test and tool commands.
- Public operator config keeps the existing `list[{operator_name: config}]` shape, and adds compatible inputs through normalization.
- Process artifacts default to the system cache and are not exposed as stable paths.
- Users can only obtain intermediate tables, manifests, relations, and debug bundles through read-only `CleanerResult` export methods.
- SQLite is the runtime state source of truth; `state.json` is a readable summary only.
- `OperatorSpec` owns static semantics and `PreviewPolicy`; it does not own default `NodePolicy`.
- `ParameterComputer` or its stages own default runtime policy and capability.
- Store action values remain `keep`, `drop`, and `review`; user-facing `clean` maps to stored `keep`; `full` is a filter alias, not a stored action.
- Runtime work must be TDD-oriented. Each task below includes its own focused tests and verification command.
- Existing unrelated working-tree changes must not be reverted or included in commits for this plan.

---

## File Structure

### New files

- `src/image_gallery/cleaning/policy.py`  
  Defines `NodePolicy`, `BatchPolicy`, `CheckpointPolicy`, `CachePolicy`, `FailurePolicy`, `RetryPolicy`, `ResourcePolicy`, `ArtifactPolicy`, `ComputerRuntimePolicy`, and `ComputerCapability`.

- `src/image_gallery/cleaning/actions.py`  
  Defines canonical action helpers: user filter normalization, `clean -> keep`, `full` handling, and invalid action errors.

- `src/image_gallery/cleaning/selection.py`  
  Normalizes user operator input into `ConfiguredOperatorSpec` objects, expands selectors, supports direct spec input, and produces user-friendly diagnostics.

- `src/image_gallery/cleaning/toml_config.py`  
  Loads TOML into `CleanerConfig`, preserving business config and runtime policy separately.

- `src/image_gallery/cleaning/preview_policy.py`  
  Defines `PreviewPolicy` and helpers that resolve policy defaults plus user overrides.

- `src/image_gallery/cleaning/graph.py`  
  Defines graph node dataclasses and `CleaningStateGraph` compilation from configured operators, registry, and policies.

- `src/image_gallery/cleaning/runtime_state.py`  
  Defines SQLite schema and `SQLiteRunStateStore`.

- `src/image_gallery/cleaning/artifacts.py`  
  Defines artifact manifests, checksum validation, tmp-to-committed promotion, and read-only export helpers.

- `src/image_gallery/cleaning/events.py`  
  Defines runtime event dataclasses and progress callback dispatch.

- `src/image_gallery/cleaning/runtime.py`  
  Defines `CleaningRuntime`, checkpoint execution, retry, resume validation, and graph execution orchestration.

- `src/image_gallery/cleaning/execution.py`  
  Defines immutable `CleanerExecution` with `plan()`, `dry_run()`, `run()`, `resume()`, and `rerun()`.

- `src/image_gallery/cleaning/result.py`  
  Defines `CleanerResult` with `status()`, `summary()`, `state()`, `result()`, `preview()`, `preview_html()`, `export()`, `export_table()`, `export_manifest()`, `export_relations()`, `export_debug_bundle()`, `explain()`, and `cleanup()`.

- `tests/unit/cleaning/test_actions.py`
- `tests/unit/cleaning/test_policy.py`
- `tests/unit/cleaning/test_selection.py`
- `tests/unit/cleaning/test_toml_config.py`
- `tests/unit/cleaning/test_preview_policy.py`
- `tests/unit/cleaning/test_graph.py`
- `tests/unit/cleaning/test_runtime_state.py`
- `tests/unit/cleaning/test_artifacts.py`
- `tests/unit/cleaning/test_events.py`
- `tests/unit/cleaning/test_execution.py`
- `tests/unit/cleaning/test_result.py`
- `tests/integration/cleaning/test_cleaner_runtime_lifecycle.py`
- `tests/integration/cleaning/test_cleaner_runtime_resume.py`
- `tests/integration/cleaning/test_cleaner_runtime_toml.py`
- `tests/integration/cleaning/test_cleaner_runtime_preview.py`

### Existing files to modify

- `src/image_gallery/operators/spec.py`  
  Add `PreviewPolicy` and `ConfiguredOperatorSpec` references to `OperatorSpec`.

- `src/image_gallery/operators/registry.py`  
  Add category listing, registry order listing, optional override registration, and selector helper support.

- `src/image_gallery/operators/builtin.py`  
  Add built-in `PreviewPolicy` defaults.

- `src/image_gallery/operators/computers/base.py`  
  Add runtime policy and capability defaults to `ParameterComputer`.

- `src/image_gallery/operators/computers/semantic.py`  
  Split semantic duplicate aggregate behavior into stages at the runtime contract level and emit artifact manifests through runtime helpers.

- `src/image_gallery/cleaning/basic.py`  
  Reduce `BasicCleaner` to a builder facade and shortcut proxy.

- `src/image_gallery/cleaning/cleaner.py`  
  Update abstract interface to reflect builder/result lifecycle or keep it minimal if the old abstract class no longer fits.

- `src/image_gallery/cleaning/html_preview.py`  
  Support operator-specific preview policy and `actions`.

- `src/image_gallery/cleaning/export.py`  
  Route clean/drop/full exports through `CleanerResult`.

- `src/image_gallery/cleaning/__init__.py`  
  Export new public types.

- Existing tests under `tests/unit/cleaning/`, `tests/unit/operators/`, and `tests/integration/cleaning/`  
  Update expected APIs from `Cleaner` return values to `CleanerResult`.

---

### Task 1: Public Contracts for Actions, Preview, Policy, and Configured Operators

**Files:**
- Create: `src/image_gallery/cleaning/actions.py`
- Create: `src/image_gallery/cleaning/policy.py`
- Create: `src/image_gallery/cleaning/preview_policy.py`
- Modify: `src/image_gallery/operators/spec.py`
- Test: `tests/unit/cleaning/test_actions.py`
- Test: `tests/unit/cleaning/test_policy.py`
- Test: `tests/unit/cleaning/test_preview_policy.py`
- Test: `tests/unit/operators/test_operator_specs.py`

**Interfaces:**
- Produces: `normalize_actions(actions: str | list[str] | None, default_actions: list[str] | None) -> ActionFilter`
- Produces: `PreviewPolicy` dataclass.
- Produces: `NodePolicy.merge(base: NodePolicy, override: NodePolicy) -> NodePolicy`.
- Produces: `ConfiguredOperatorSpec` dataclass with `operator_config_hash: str`.
- Consumes: existing `hash_config(config: dict[str, object]) -> str`.

- [ ] **Step 1: Write failing tests for action normalization**

Add to `tests/unit/cleaning/test_actions.py`:

```python
import pytest

from image_gallery.cleaning.actions import ActionFilter, normalize_actions


def test_normalize_actions_maps_clean_to_keep() -> None:
    action_filter = normalize_actions("clean", default_actions=None)

    assert action_filter == ActionFilter(stored_actions=frozenset({"keep"}), include_all=False)


def test_normalize_actions_supports_multiple_actions() -> None:
    action_filter = normalize_actions(["drop", "review"], default_actions=None)

    assert action_filter == ActionFilter(stored_actions=frozenset({"drop", "review"}), include_all=False)


def test_normalize_actions_full_is_include_all() -> None:
    action_filter = normalize_actions("full", default_actions=["drop"])

    assert action_filter == ActionFilter(stored_actions=frozenset(), include_all=True)


def test_normalize_actions_rejects_full_mixed_with_actions() -> None:
    with pytest.raises(ValueError, match="full cannot be combined"):
        normalize_actions(["full", "drop"], default_actions=None)


def test_normalize_actions_uses_defaults_when_actions_missing() -> None:
    action_filter = normalize_actions(None, default_actions=["drop", "review"])

    assert action_filter == ActionFilter(stored_actions=frozenset({"drop", "review"}), include_all=False)
```

- [ ] **Step 2: Run action tests and verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_actions.py -q`  
Expected: FAIL with `ModuleNotFoundError: No module named 'image_gallery.cleaning.actions'`.

- [ ] **Step 3: Implement action helpers**

Create `src/image_gallery/cleaning/actions.py`:

```python
from dataclasses import dataclass
from typing import Iterable


_USER_TO_STORED_ACTION = {
    "clean": "keep",
    "keep": "keep",
    "drop": "drop",
    "review": "review",
}


@dataclass(frozen=True)
class ActionFilter:
    """用户 action 筛选归一化后的存储层表达。"""

    stored_actions: frozenset[str]
    include_all: bool = False


def normalize_actions(
    actions: str | Iterable[str] | None,
    default_actions: list[str] | None,
) -> ActionFilter:
    """把用户传入的 actions 归一化为存储层 keep/drop/review。"""
    selected = default_actions if actions is None else actions
    if selected is None:
        return ActionFilter(stored_actions=frozenset(), include_all=True)
    if isinstance(selected, str):
        values = [selected]
    else:
        values = list(selected)
    normalized_values = [str(value).strip().lower() for value in values]
    if not normalized_values:
        return ActionFilter(stored_actions=frozenset(), include_all=True)
    if "full" in normalized_values:
        if len(normalized_values) != 1:
            raise ValueError("full cannot be combined with other actions")
        return ActionFilter(stored_actions=frozenset(), include_all=True)
    unknown = [value for value in normalized_values if value not in _USER_TO_STORED_ACTION]
    if unknown:
        raise ValueError(f"unknown actions: {unknown}")
    return ActionFilter(
        stored_actions=frozenset(_USER_TO_STORED_ACTION[value] for value in normalized_values),
        include_all=False,
    )
```

- [ ] **Step 4: Write failing tests for `PreviewPolicy`, `NodePolicy`, and `ConfiguredOperatorSpec`**

Add to `tests/unit/cleaning/test_preview_policy.py`:

```python
from image_gallery.cleaning.preview_policy import PreviewPolicy, resolve_preview_policy


def test_resolve_preview_policy_keeps_explicit_overrides() -> None:
    policy = PreviewPolicy(
        default_actions=["drop"],
        caption_columns=["blur_score"],
        groupby=None,
        include_group_context=False,
        sort_by=["blur_score"],
        ascending=True,
    )

    resolved = resolve_preview_policy(
        policy,
        actions=["review"],
        caption_columns=None,
        groupby="custom_group",
        include_group_context=None,
        sort_by=None,
        ascending=None,
    )

    assert resolved.actions == ["review"]
    assert resolved.caption_columns == ["blur_score"]
    assert resolved.groupby == "custom_group"
    assert resolved.sort_by == ["blur_score"]
```

Add to `tests/unit/cleaning/test_policy.py`:

```python
from image_gallery.cleaning.policy import BatchPolicy, NodePolicy


def test_node_policy_merge_uses_override_values() -> None:
    base = NodePolicy(batch=BatchPolicy(size=128))
    override = NodePolicy(batch=BatchPolicy(size=32))

    merged = NodePolicy.merge(base, override)

    assert merged.batch.size == 32


def test_node_policy_preset_balanced_has_checkpoint_enabled() -> None:
    policy = NodePolicy.preset("balanced")

    assert policy.checkpoint.enabled is True
    assert policy.cache.scope == "system"
```

Extend `tests/unit/operators/test_operator_specs.py`:

```python
from image_gallery.cleaning.preview_policy import PreviewPolicy
from image_gallery.operators.spec import ConfiguredOperatorSpec, OperatorSpec


def _demo_operator_spec() -> OperatorSpec:
    return OperatorSpec(
        name="quality.demo_check",
        category="quality",
        required_parameters=["score"],
        evaluation_columns=["score", "demo_action", "demo_reason"],
        default_config={"threshold": 1.0, "action": "review"},
        action_column="demo_action",
        reason_column="demo_reason",
        evaluator=lambda frame, config: frame[["image_id", "score"]].assign(
            demo_action="keep",
            demo_reason="",
        ),
        preview_policy=PreviewPolicy(default_actions=["review"], caption_columns=["score"]),
    )


def test_configured_operator_spec_hash_excludes_policy() -> None:
    configured = ConfiguredOperatorSpec.from_spec(
        _demo_operator_spec(),
        config={"threshold": 2.0, "action": "drop"},
        source="python",
    )

    assert configured.operator_name == "quality.demo_check"
    assert configured.config["threshold"] == 2.0
    assert len(configured.operator_config_hash) == 64
```

- [ ] **Step 5: Run contract tests and verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_preview_policy.py tests/unit/cleaning/test_policy.py tests/unit/operators/test_operator_specs.py -q`  
Expected: FAIL because `PreviewPolicy`, `NodePolicy`, or `ConfiguredOperatorSpec` is not defined.

- [ ] **Step 6: Implement public contract dataclasses**

Create `src/image_gallery/cleaning/preview_policy.py` with `PreviewPolicy`, `ResolvedPreviewOptions`, and `resolve_preview_policy`.  
Create `src/image_gallery/cleaning/policy.py` with all policy dataclasses and `NodePolicy.preset`.  
Modify `src/image_gallery/operators/spec.py` to add `preview_policy: PreviewPolicy = field(default_factory=PreviewPolicy)` and `ConfiguredOperatorSpec`.

Implementation must include these signatures:

```python
@dataclass(frozen=True)
class PreviewPolicy:
    default_actions: list[str] | None = None
    caption_columns: list[str] | None = None
    groupby: str | None = None
    include_group_context: bool = False
    sort_by: list[str] | None = None
    ascending: bool | list[bool] = True
    max_rows: int = 200
    max_groups: int = 50
    max_items_per_group: int = 20
    thumbnail_size: int = 320
    columns_per_row: int = 6
```

```python
@dataclass(frozen=True)
class ConfiguredOperatorSpec:
    spec: OperatorSpec
    config: dict[str, object]
    source: str
    operator_config_hash: str

    @property
    def operator_name(self) -> str:
        return self.spec.name
```

- [ ] **Step 7: Run Task 1 tests**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_actions.py tests/unit/cleaning/test_preview_policy.py tests/unit/cleaning/test_policy.py tests/unit/operators/test_operator_specs.py -q`  
Expected: PASS.

- [ ] **Step 8: Commit Task 1**

```bash
git add src/image_gallery/cleaning/actions.py \
  src/image_gallery/cleaning/policy.py \
  src/image_gallery/cleaning/preview_policy.py \
  src/image_gallery/operators/spec.py \
  tests/unit/cleaning/test_actions.py \
  tests/unit/cleaning/test_policy.py \
  tests/unit/cleaning/test_preview_policy.py \
  tests/unit/operators/test_operator_specs.py
git commit -m "feat: add cleaner runtime public contracts"
```

---

### Task 2: Operator Selection, TOML Config, and Built-In Preview Policies

**Files:**
- Create: `src/image_gallery/cleaning/selection.py`
- Create: `src/image_gallery/cleaning/toml_config.py`
- Modify: `pyproject.toml`
- Modify: `src/image_gallery/operators/registry.py`
- Modify: `src/image_gallery/operators/builtin.py`
- Test: `tests/unit/cleaning/test_selection.py`
- Test: `tests/unit/cleaning/test_toml_config.py`
- Test: `tests/unit/operators/test_builtin_specs.py`

**Interfaces:**
- Consumes: `ConfiguredOperatorSpec`, `NodePolicy`, `PreviewPolicy`.
- Produces: `OperatorSelectorInput` type alias.
- Produces: `select_operators(operators, registry, overrides=None, override=False) -> list[ConfiguredOperatorSpec]`.
- Produces: `CleanerConfig.from_toml(path: str | Path) -> CleanerConfig`.

- [ ] **Step 1: Write failing selector tests**

Add to `tests/unit/cleaning/test_selection.py`:

```python
import pytest

from image_gallery.cleaning.selection import select_operators
from image_gallery.operators.builtin import create_default_registry


def test_select_all_expands_registry_order() -> None:
    selected = select_operators("ALL", create_default_registry())

    assert "format.decode_check" in [item.operator_name for item in selected]
    assert "duplicate.semantic_duplicate_check" in [item.operator_name for item in selected]


def test_select_category_expands_matching_operators() -> None:
    selected = select_operators(["QUALITY"], create_default_registry())

    assert {item.spec.category for item in selected} == {"quality"}
    assert "quality.blur_check" in [item.operator_name for item in selected]


def test_select_name_and_category_deduplicates() -> None:
    selected = select_operators(["quality.blur_check", "QUALITY"], create_default_registry())

    names = [item.operator_name for item in selected]
    assert names.count("quality.blur_check") == 1


def test_select_unknown_category_has_helpful_error() -> None:
    with pytest.raises(ValueError, match="available categories"):
        select_operators(["NOT_A_CATEGORY"], create_default_registry())
```

- [ ] **Step 2: Run selector tests and verify failure**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_selection.py -q`  
Expected: FAIL because `image_gallery.cleaning.selection` is missing.

- [ ] **Step 3: Implement registry category helpers and selection**

Modify `src/image_gallery/operators/registry.py` to add:

```python
def list_operator_specs(self) -> list[OperatorSpec]:
    """按注册顺序返回逻辑算子规格。"""
    return list(self._operators.values())


def list_categories(self) -> list[str]:
    """返回当前 registry 中的逻辑算子 category。"""
    return sorted({spec.category for spec in self._operators.values()})
```

Create `src/image_gallery/cleaning/selection.py` with selector expansion and config merge. Category selector matching must use uppercase category names.

- [ ] **Step 4: Write failing TOML tests**

Add to `tests/unit/cleaning/test_toml_config.py`:

```python
from pathlib import Path

from image_gallery.cleaning.toml_config import CleanerConfig


def test_cleaner_config_from_toml_separates_business_and_policy(tmp_path: Path) -> None:
    config_path = tmp_path / "cleaning.toml"
    config_path.write_text(
        """
[cleaner]
operators = ["QUALITY"]

[node_policy.batch]
size = 128

[[operator]]
name = "quality.blur_check"
min_score = 120.0
action = "drop"

[operator_policies."quality.blur_check".batch]
size = 32
""".strip(),
        encoding="utf-8",
    )

    config = CleanerConfig.from_toml(config_path)

    assert config.operators == ["QUALITY"]
    assert config.operator_configs["quality.blur_check"]["min_score"] == 120.0
    assert config.node_policy.batch.size == 128
    assert config.operator_policies["quality.blur_check"].batch.size == 32
```

- [ ] **Step 5: Run TOML tests and verify failure**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_toml_config.py -q`  
Expected: FAIL because `CleanerConfig` is missing.

- [ ] **Step 6: Implement `CleanerConfig` TOML parser**

Modify `pyproject.toml` to add `tomli>=2.0` because the project supports Python 3.10 and stdlib `tomllib` is only available from Python 3.11. Create `src/image_gallery/cleaning/toml_config.py` and import TOML support with this compatibility pattern:

```python
try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib
```

Parser output must be a dataclass:

```python
@dataclass(frozen=True)
class CleanerConfig:
    operators: str | list[object]
    operator_configs: dict[str, dict[str, object]]
    node_policy: NodePolicy
    operator_policies: dict[str, NodePolicy]

    @classmethod
    def from_toml(cls, path: str | Path) -> "CleanerConfig":
        payload = _load_toml_mapping(path)
        return cls.from_mapping(payload)

    @classmethod
    def from_mapping(cls, payload: dict[str, object]) -> "CleanerConfig":
        return _parse_cleaner_config_mapping(payload)
```

The implementation must keep operator business config under `operator_configs` and runtime config under `node_policy` / `operator_policies`.

- [ ] **Step 7: Add built-in `PreviewPolicy` defaults**

Modify `src/image_gallery/operators/builtin.py` so every `OperatorSpec` receives a `preview_policy`. Extend `tests/unit/operators/test_builtin_specs.py`:

```python
from image_gallery.operators.builtin import create_default_registry


def test_builtin_specs_have_preview_policy() -> None:
    registry = create_default_registry()

    for spec in registry.list_operator_specs():
        assert spec.preview_policy is not None


def test_duplicate_specs_group_preview_by_duplicate_group() -> None:
    registry = create_default_registry()

    spec = registry.get_operator("duplicate.semantic_duplicate_check")

    assert spec.preview_policy.groupby == "semantic_duplicate_group_id"
    assert spec.preview_policy.include_group_context is True
```

- [ ] **Step 8: Run Task 2 tests**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_selection.py tests/unit/cleaning/test_toml_config.py tests/unit/operators/test_builtin_specs.py -q`  
Expected: PASS.

- [ ] **Step 9: Commit Task 2**

```bash
git add src/image_gallery/cleaning/selection.py \
  src/image_gallery/cleaning/toml_config.py \
  pyproject.toml \
  src/image_gallery/operators/registry.py \
  src/image_gallery/operators/builtin.py \
  tests/unit/cleaning/test_selection.py \
  tests/unit/cleaning/test_toml_config.py \
  tests/unit/operators/test_builtin_specs.py
git commit -m "feat: add cleaner config and operator selection"
```

---

### Task 3: StateGraph Compiler and Policy Projection

**Files:**
- Create: `src/image_gallery/cleaning/graph.py`
- Modify: `src/image_gallery/operators/computers/base.py`
- Test: `tests/unit/cleaning/test_graph.py`
- Test: `tests/unit/operators/test_parameter_computer_contract.py`

**Interfaces:**
- Consumes: `ConfiguredOperatorSpec`, `OperatorRegistry`, `NodePolicy`, `ComputerRuntimePolicy`, `ComputerCapability`.
- Produces: `CleaningStateGraph.compile(configured_operators, registry, node_policy, operator_policies) -> CleaningStateGraph`.
- Produces: `GraphNode` dataclass.
- Produces: `plan_hash: str`.

- [ ] **Step 1: Write failing graph tests**

Add to `tests/unit/cleaning/test_graph.py`:

```python
import pandas as pd

from image_gallery.cleaning.graph import CleaningStateGraph
from image_gallery.cleaning.selection import select_operators
from image_gallery.operators.builtin import create_default_registry


def test_state_graph_orders_by_parameter_dependencies() -> None:
    registry = create_default_registry()
    operators = select_operators([{"duplicate.exact_duplicate_check": {}}], registry)

    graph = CleaningStateGraph.compile(operators, registry)

    node_ids = [node.node_id for node in graph.nodes]
    assert node_ids.index("parameter.image_hash_computer") < node_ids.index("parameter.duplicate_group_computer")
    assert node_ids.index("parameter.duplicate_group_computer") < node_ids.index(
        "evaluation.duplicate.exact_duplicate_check"
    )
    assert node_ids[-1] == "merge.final_action"


def test_state_graph_includes_evaluation_and_merge_nodes() -> None:
    registry = create_default_registry()
    operators = select_operators([{"quality.blur_check": {}}], registry)

    graph = CleaningStateGraph.compile(operators, registry)

    assert "evaluation.quality.blur_check" in [node.node_id for node in graph.nodes]
    assert "merge.final_action" in [node.node_id for node in graph.nodes]


def test_state_graph_rejects_conflicting_shared_node_policy() -> None:
    registry = create_default_registry()
    operators = select_operators(["quality.blur_check", "quality.contrast_check"], registry)

    with pytest.raises(ValueError, match="conflicting operator policy"):
        CleaningStateGraph.compile(
            operators,
            registry,
            operator_policies={
                "quality.blur_check": NodePolicy(batch=BatchPolicy(size=64)),
                "quality.contrast_check": NodePolicy(batch=BatchPolicy(size=256)),
            },
        )
```

Include these imports in the file:

```python
import pytest

from image_gallery.cleaning.policy import BatchPolicy, NodePolicy
```

- [ ] **Step 2: Run graph tests and verify failure**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_graph.py -q`  
Expected: FAIL because `CleaningStateGraph` is missing.

- [ ] **Step 3: Add runtime policy defaults to `ParameterComputer`**

Modify `src/image_gallery/operators/computers/base.py`:

```python
class ParameterComputer(ABC):
    """参数计算单元基类。"""

    name: str
    execution_mode: ExecutionMode
    produced_parameters: frozenset[str]
    required_parameters: frozenset[str] = frozenset()
    config_parameters: frozenset[str] = frozenset()
    runtime_policy: ComputerRuntimePolicy = ComputerRuntimePolicy()
    capability: ComputerCapability = ComputerCapability()
```

Add contract tests in `tests/unit/operators/test_parameter_computer_contract.py` to assert per-image defaults support batch checkpoint and aggregate defaults support whole-node or stage.

- [ ] **Step 4: Implement `CleaningStateGraph`**

Create `src/image_gallery/cleaning/graph.py` with:

```python
@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: str
    operator_name: str | None
    computer_name: str | None
    stage_name: str | None
    execution_mode: ExecutionMode | None
    required_parameters: frozenset[str]
    produced_parameters: frozenset[str]
    config_hash: str
    policy_hash: str
    upstream_node_ids: tuple[str, ...]
    checkpoint_strategy: str


@dataclass(frozen=True)
class CleaningStateGraph:
    nodes: tuple[GraphNode, ...]
    plan_hash: str

    @classmethod
    def compile(
        cls,
        configured_operators: list[ConfiguredOperatorSpec],
        registry: OperatorRegistry,
        node_policy: NodePolicy | None = None,
        operator_policies: dict[str, NodePolicy] | None = None,
    ) -> "CleaningStateGraph":
        return compile_state_graph(
            configured_operators=configured_operators,
            registry=registry,
            node_policy=node_policy,
            operator_policies=operator_policies,
        )
```

Implementation should adapt logic from `CleaningRunPlanner` and include evaluation/merge nodes.

- [ ] **Step 5: Run Task 3 tests**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_graph.py tests/unit/operators/test_parameter_computer_contract.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add src/image_gallery/cleaning/graph.py \
  src/image_gallery/operators/computers/base.py \
  tests/unit/cleaning/test_graph.py \
  tests/unit/operators/test_parameter_computer_contract.py
git commit -m "feat: compile cleaner state graph"
```

---

### Task 4: SQLite Runtime State Store and Artifact Manager

**Files:**
- Create: `src/image_gallery/cleaning/runtime_state.py`
- Create: `src/image_gallery/cleaning/artifacts.py`
- Test: `tests/unit/cleaning/test_runtime_state.py`
- Test: `tests/unit/cleaning/test_artifacts.py`

**Interfaces:**
- Produces: `SQLiteRunStateStore.initialize(run_dir: Path, run_record: RunRecord) -> SQLiteRunStateStore`.
- Produces: `SQLiteRunStateStore.record_node_started(node_id: str) -> None`.
- Produces: `SQLiteRunStateStore.record_event(event: RuntimeEvent) -> None`.
- Produces: `ArtifactManager.commit_dataframe_artifact(artifact_id, artifact_type, owner_node_id, frame, relative_path, config_hash, policy_hash) -> ArtifactManifest`.
- Consumes: `GraphNode`, `CleaningStateGraph`.

- [ ] **Step 1: Write failing SQLite tests**

Add to `tests/unit/cleaning/test_runtime_state.py`:

```python
from pathlib import Path

from image_gallery.cleaning.runtime_state import RunRecord, SQLiteRunStateStore


def test_sqlite_store_initializes_run_and_events(tmp_path: Path) -> None:
    store = SQLiteRunStateStore.initialize(
        tmp_path,
        RunRecord(
            run_id="run-1",
            cleaner_type="basic",
            status="running",
            dataset_fingerprint="fp",
            plan_hash="plan",
            label="smoke",
            tags=["sample"],
            sample_size=None,
            sample_rule=None,
        ),
    )

    store.record_event("run_started", message="started", payload={"phase": 1})
    loaded = store.load_run("run-1")
    events = store.list_events("run-1")

    assert loaded.label == "smoke"
    assert loaded.tags == ["sample"]
    assert events[0].event_type == "run_started"
```

- [ ] **Step 2: Run SQLite tests and verify failure**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_runtime_state.py -q`  
Expected: FAIL because `runtime_state` is missing.

- [ ] **Step 3: Implement SQLite schema**

Create `src/image_gallery/cleaning/runtime_state.py` using stdlib `sqlite3`. Create tables named exactly:

```text
cleaning_run
graph_node
stage_run
batch_run
artifact
run_event
```

The `cleaning_run` table must include `label`, `tags_json`, `sample_size`, and `sample_rule_json`.

- [ ] **Step 4: Write failing artifact manager tests**

Add to `tests/unit/cleaning/test_artifacts.py`:

```python
from pathlib import Path

import pandas as pd
import pytest

from image_gallery.cleaning.artifacts import ArtifactManager


def test_artifact_manager_commits_dataframe_with_manifest(tmp_path: Path) -> None:
    manager = ArtifactManager(tmp_path)
    frame = pd.DataFrame({"image_id": ["img-1"], "score": [1.0]})

    manifest = manager.commit_dataframe_artifact(
        artifact_id="artifact-1",
        artifact_type="parameter_part",
        owner_node_id="parameter.demo",
        frame=frame,
        relative_path="tables/parameter_part.parquet",
        config_hash="config",
        policy_hash="policy",
    )

    assert (tmp_path / "tables" / "parameter_part.parquet").exists()
    assert Path(manifest.manifest_uri).exists()
    assert manifest.row_count == 1
    assert manifest.commit_marker == "committed"


def test_artifact_manager_rejects_missing_manifest(tmp_path: Path) -> None:
    manager = ArtifactManager(tmp_path)

    with pytest.raises(FileNotFoundError):
        manager.validate_manifest(tmp_path / "missing.json")
```

- [ ] **Step 5: Implement artifact manager**

Create `src/image_gallery/cleaning/artifacts.py` with `ArtifactManifest` and `ArtifactManager`. Use sha256 over file bytes for checksum. The manifest JSON must include `artifact_id`, `artifact_type`, `owner_node_id`, `schema_version`, `schema_hash`, `config_hash`, `policy_hash`, `row_count`, `part_files`, `checksum`, `created_at`, and `commit_marker`.

- [ ] **Step 6: Run Task 4 tests**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_runtime_state.py tests/unit/cleaning/test_artifacts.py -q`  
Expected: PASS.

- [ ] **Step 7: Commit Task 4**

```bash
git add src/image_gallery/cleaning/runtime_state.py \
  src/image_gallery/cleaning/artifacts.py \
  tests/unit/cleaning/test_runtime_state.py \
  tests/unit/cleaning/test_artifacts.py
git commit -m "feat: add cleaner runtime state and artifacts"
```

---

### Task 5: Runtime Events, Progress, Retry, and Component Execution

**Files:**
- Create: `src/image_gallery/cleaning/events.py`
- Create: `src/image_gallery/cleaning/runtime.py`
- Test: `tests/unit/cleaning/test_events.py`
- Test: `tests/unit/cleaning/test_runtime_component.py`

**Interfaces:**
- Produces: `RuntimeEvent` dataclass.
- Produces: `ProgressReporter`.
- Produces: `CleaningRuntime.run_graph(graph, dataset, run_options) -> RuntimeRunResult`.
- Consumes: `SQLiteRunStateStore`, `ArtifactManager`, `CleaningStateGraph`.

- [ ] **Step 1: Write failing progress event tests**

Add to `tests/unit/cleaning/test_events.py`:

```python
from image_gallery.cleaning.events import ProgressReporter, RuntimeEvent


def test_progress_reporter_sends_callback_events() -> None:
    received: list[RuntimeEvent] = []
    reporter = ProgressReporter(callback=received.append)

    reporter.emit(
        event_type="node_started",
        run_id="run-1",
        node_id="parameter.demo",
        message="started",
    )

    assert received[0].event_type == "node_started"
    assert received[0].node_id == "parameter.demo"
```

- [ ] **Step 2: Implement events**

Create `src/image_gallery/cleaning/events.py` with `RuntimeEvent` and `ProgressReporter`. `ProgressReporter.emit` must accept `event_type`, `run_id`, `node_id`, `message`, and optional `payload`.

- [ ] **Step 3: Write failing runtime component tests with fake computer**

Add to `tests/unit/cleaning/test_runtime_component.py`:

```python
from pathlib import Path

import pandas as pd

from image_gallery.cleaning.runtime import CleaningRuntime, RunOptions


def test_runtime_retries_stage_once_then_completes(tmp_path: Path, tiny_dataset) -> None:
    runtime = CleaningRuntime(cache_root=tmp_path)
    options = RunOptions(run_id="run-1", retry_max_attempts=2)

    result = runtime.run_fake_stage_for_test(
        dataset=tiny_dataset,
        options=options,
        fail_first_attempt=True,
    )

    assert result.status == "completed"
    assert result.attempt_count == 2
    assert runtime.state_store.list_events("run-1")[-1].event_type == "run_completed"
```

If `tiny_dataset` does not exist, create a local pytest fixture inside the test file that writes a two-row parquet dataset with tiny PNG files.

- [ ] **Step 4: Implement minimal runtime component behavior**

Create `src/image_gallery/cleaning/runtime.py` with `RunOptions`, `RuntimeRunResult`, and `CleaningRuntime`. Include a test-only helper `run_fake_stage_for_test` to validate retry and state/event wiring before full graph execution exists. Keep this helper private by naming it `_run_fake_stage_for_test` if tests can import protected members locally; otherwise keep the public method and mark it as test support in the docstring.

- [ ] **Step 5: Run Task 5 tests**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_events.py tests/unit/cleaning/test_runtime_component.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```bash
git add src/image_gallery/cleaning/events.py \
  src/image_gallery/cleaning/runtime.py \
  tests/unit/cleaning/test_events.py \
  tests/unit/cleaning/test_runtime_component.py
git commit -m "feat: add cleaner runtime event execution"
```

---

### Task 6: CleanerExecution and BasicCleaner Builder Refactor

**Files:**
- Create: `src/image_gallery/cleaning/execution.py`
- Create: `src/image_gallery/cleaning/result.py`
- Modify: `src/image_gallery/cleaning/basic.py`
- Modify: `src/image_gallery/cleaning/cleaner.py`
- Modify: `src/image_gallery/cleaning/__init__.py`
- Test: `tests/unit/cleaning/test_execution.py`
- Test: `tests/unit/cleaning/test_basic_cleaner.py`
- Test: `tests/integration/cleaning/test_cleaner_runtime_lifecycle.py`

**Interfaces:**
- Produces: `BasicCleaner.compile() -> CleanerExecution`.
- Produces: `BasicCleaner.run(dataset, **run_options) -> CleanerResult`.
- Produces: `CleanerExecution.plan() -> pd.DataFrame`.
- Produces: `CleanerExecution.dry_run(dataset) -> DryRunResult`.
- Consumes: `CleaningStateGraph`, `CleaningRuntime`, `CleanerConfig`.

- [ ] **Step 1: Write failing execution tests**

Add to `tests/unit/cleaning/test_execution.py`:

```python
from image_gallery.cleaning import BasicCleaner
from image_gallery.cleaning.execution import CleanerExecution


def test_basic_cleaner_compile_returns_execution() -> None:
    execution = BasicCleaner([{"format.decode_check": {}}]).compile()

    assert isinstance(execution, CleanerExecution)
    assert "evaluation.format.decode_check" in execution.plan()["node_id"].tolist()


def test_dry_run_reports_selected_operator() -> None:
    execution = BasicCleaner([{"format.decode_check": {}}]).compile()

    dry_run = execution.dry_run(dataset=None)

    assert "format.decode_check" in dry_run.selected_operators
    assert dry_run.errors == []
```

- [ ] **Step 2: Run execution tests and verify failure**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_execution.py -q`  
Expected: FAIL because `CleanerExecution` is missing or `compile()` returns `BasicCleaner`.

- [ ] **Step 3: Implement `CleanerExecution`**

Create `src/image_gallery/cleaning/execution.py` with:

```python
@dataclass(frozen=True)
class DryRunResult:
    selected_operators: list[str]
    expanded_selectors: list[str]
    graph_nodes: list[str]
    policy_overrides: dict[str, object]
    warnings: list[str]
    errors: list[str]
    estimated_artifacts: list[str]
    preview_policies: dict[str, object]


class CleanerExecution:
    def plan(self) -> pd.DataFrame:
        return self.graph.to_frame()

    def dry_run(self, dataset: Dataset | None = None) -> DryRunResult:
        return build_dry_run_result(self.graph, self.configured_operators, dataset)

    def run(self, dataset: Dataset, **run_options: object) -> CleanerResult:
        runtime_result = self.runtime.run_graph(self.graph, dataset, run_options)
        return CleanerResult(run_id=runtime_result.run_id, cache_root=runtime_result.cache_root)

    def resume(self, *, dataset: Dataset, run_id: str | None = None, result: CleanerResult | None = None) -> CleanerResult:
        runtime_result = self.runtime.resume_graph(self.graph, dataset, run_id=run_id, result=result)
        return CleanerResult(run_id=runtime_result.run_id, cache_root=runtime_result.cache_root)

    def rerun(self, result: CleanerResult, operators: object, overwrite: bool = False) -> CleanerResult:
        runtime_result = self.runtime.rerun_evaluation(self.graph, result, operators, overwrite=overwrite)
        return CleanerResult(run_id=runtime_result.run_id, cache_root=runtime_result.cache_root)
```

Create `src/image_gallery/cleaning/result.py` in this task with a minimal `CleanerResult` shell:

```python
@dataclass(frozen=True)
class CleanerResult:
    run_id: str
    cache_root: Path

    def status(self) -> str:
        return read_result_status(self.cache_root)
```

Task 7 expands this class with full export, preview, explain, and cleanup methods.

- [ ] **Step 4: Refactor `BasicCleaner` to builder**

Modify `src/image_gallery/cleaning/basic.py` so:

```python
def compile(self) -> CleanerExecution:
    configured = select_operators(self._operators, self._registry)
    graph = CleaningStateGraph.compile(
        configured,
        self._registry,
        node_policy=self._node_policy,
        operator_policies=self._operator_policies,
    )
    return CleanerExecution(graph=graph, registry=self._registry, configured_operators=configured)
```

`BasicCleaner.run(dataset, **run_options)` must return `self.compile().run(dataset, **run_options)`.

- [ ] **Step 5: Add lifecycle integration test**

Create `tests/integration/cleaning/test_cleaner_runtime_lifecycle.py` with a tiny local dataset and:

```python
def test_basic_cleaner_run_returns_result_and_hides_process_outputs(tmp_path: Path) -> None:
    dataset = _tiny_dataset(tmp_path)
    result = BasicCleaner([{"format.decode_check": {}}]).run(dataset, label="smoke")

    assert result.status() in {"completed", "running"}
    assert not (tmp_path / "parameter_table.parquet").exists()
```

Use a local helper `_tiny_dataset` that writes two PNG files and a raw parquet.

- [ ] **Step 6: Run Task 6 tests**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_execution.py tests/unit/cleaning/test_basic_cleaner.py tests/integration/cleaning/test_cleaner_runtime_lifecycle.py -q`  
Expected: PASS.

- [ ] **Step 7: Commit Task 6**

```bash
git add src/image_gallery/cleaning/execution.py \
  src/image_gallery/cleaning/result.py \
  src/image_gallery/cleaning/basic.py \
  src/image_gallery/cleaning/cleaner.py \
  src/image_gallery/cleaning/__init__.py \
  tests/unit/cleaning/test_execution.py \
  tests/unit/cleaning/test_basic_cleaner.py \
  tests/integration/cleaning/test_cleaner_runtime_lifecycle.py
git commit -m "feat: refactor cleaner into execution lifecycle"
```

---

### Task 7: CleanerResult Export, Preview, Explain, and Cleanup

**Files:**
- Modify: `src/image_gallery/cleaning/result.py`
- Modify: `src/image_gallery/cleaning/export.py`
- Modify: `src/image_gallery/cleaning/html_preview.py`
- Modify: `src/image_gallery/cleaning/preview.py`
- Test: `tests/unit/cleaning/test_result.py`
- Test: `tests/unit/cleaning/test_html_preview.py`
- Test: `tests/integration/cleaning/test_cleaner_runtime_preview.py`

**Interfaces:**
- Produces: `CleanerResult.status() -> str`.
- Produces: `CleanerResult.export(kind: str, path: str | Path) -> Dataset`.
- Produces: `CleanerResult.preview_html(path, operator_name=None, actions=None, filters=None, groupby=None, include_group_context=None, sort_by=None, ascending=None, caption_columns=None) -> Path`.
- Produces: `CleanerResult.explain(image_id: str) -> dict[str, object]`.
- Consumes: runtime backing files from cache root, `PreviewPolicy`, `normalize_actions`.

- [ ] **Step 1: Write failing result tests**

Add to `tests/unit/cleaning/test_result.py`:

```python
from pathlib import Path

import pandas as pd

from image_gallery.cleaning.result import CleanerResult


def test_result_export_table_writes_copy(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    tables_dir = run_dir / "tables"
    tables_dir.mkdir(parents=True)
    pd.DataFrame({"image_id": ["img-1"], "decode_ok": [True]}).to_parquet(
        tables_dir / "parameter_table.parquet",
        index=False,
    )
    result = CleanerResult(run_id="run-1", cache_root=run_dir)

    output = result.export_table("parameter", tmp_path / "parameter_copy.parquet")

    assert output == tmp_path / "parameter_copy.parquet"
    assert pd.read_parquet(output)["image_id"].tolist() == ["img-1"]


def test_result_does_not_expose_work_dir() -> None:
    result = CleanerResult(run_id="run-1", cache_root=Path("/tmp/run"))

    assert not hasattr(result, "work_dir")
```

- [ ] **Step 2: Implement `CleanerResult` table and manifest export**

Create `src/image_gallery/cleaning/result.py`. It may store internal `cache_root`, but must not expose it as a public `work_dir` property. Implement `export_table`, `export_manifest`, and `cleanup`.

- [ ] **Step 3: Write failing preview integration test**

Add to `tests/integration/cleaning/test_cleaner_runtime_preview.py`:

```python
from pathlib import Path

from image_gallery.cleaning import BasicCleaner


def test_result_preview_html_supports_operator_actions(tmp_path: Path) -> None:
    dataset = _tiny_dataset(tmp_path)
    result = BasicCleaner([{"format.decode_check": {}}]).run(dataset)

    output = result.preview_html(
        tmp_path / "decode_drop.html",
        operator_name="format.decode_check",
        actions="drop",
    )

    html = output.read_text(encoding="utf-8")
    assert "decode" in html
```

Include `_tiny_dataset` helper or import the helper introduced in Task 6.

- [ ] **Step 4: Implement preview/explain/export**

Update preview helpers to use `operator_name`, resolved preview policy, and `actions`. Implement `explain(image_id)` from evaluation table, operator outputs, relation manifests, and final merge columns.

- [ ] **Step 5: Run Task 7 tests**

Run: `.venv/bin/python -m pytest tests/unit/cleaning/test_result.py tests/unit/cleaning/test_html_preview.py tests/integration/cleaning/test_cleaner_runtime_preview.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit Task 7**

```bash
git add src/image_gallery/cleaning/result.py \
  src/image_gallery/cleaning/export.py \
  src/image_gallery/cleaning/html_preview.py \
  src/image_gallery/cleaning/preview.py \
  tests/unit/cleaning/test_result.py \
  tests/unit/cleaning/test_html_preview.py \
  tests/integration/cleaning/test_cleaner_runtime_preview.py
git commit -m "feat: add cleaner result exports and preview"
```

---

### Task 8: Full Runtime Resume, Rerun, and Semantic Artifact Integration

**Files:**
- Modify: `src/image_gallery/cleaning/runtime.py`
- Modify: `src/image_gallery/cleaning/scheduler.py`
- Modify: `src/image_gallery/operators/computers/semantic.py`
- Modify: `src/image_gallery/operators/computers/duplicate.py`
- Test: `tests/integration/cleaning/test_cleaner_runtime_resume.py`
- Test: `tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py`

**Interfaces:**
- Consumes: `SQLiteRunStateStore`, `ArtifactManager`, `CleaningStateGraph`.
- Produces: resume validation by dataset fingerprint, plan hash, parameter config hash, policy hash, artifact manifest, and sample rule.
- Produces: evaluation-only `rerun()`.

- [ ] **Step 1: Write failing resume integration tests**

Create `tests/integration/cleaning/test_cleaner_runtime_resume.py`:

```python
from pathlib import Path

import pytest

from image_gallery.cleaning import BasicCleaner


def test_resume_reuses_completed_nodes(tmp_path: Path) -> None:
    dataset = _tiny_dataset(tmp_path)
    execution = BasicCleaner([{"format.decode_check": {}}]).compile()
    result = execution.run(dataset)

    resumed = execution.resume(dataset=dataset, run_id=result.run_id)

    assert resumed.status() == "completed"


def test_resume_rejects_sample_rule_mismatch(tmp_path: Path) -> None:
    dataset = _tiny_dataset(tmp_path)
    execution = BasicCleaner([{"format.decode_check": {}}]).compile()
    result = execution.run(dataset, sample={"n": 1, "random_state": 1})

    with pytest.raises(ValueError, match="sample rule"):
        execution.resume(dataset=dataset, run_id=result.run_id, sample={"n": 1, "random_state": 2})
```

- [ ] **Step 2: Implement resume validation**

In `src/image_gallery/cleaning/runtime.py`, implement resume lookup by `run_id` and by `CleanerResult`. Validate dataset fingerprint, plan hash, node config hash, policy hash, artifact manifests, and sample rule before reusing any completed node.

- [ ] **Step 3: Write failing rerun tests**

Extend `tests/integration/cleaning/test_cleaner_runtime_resume.py`:

```python
def test_rerun_allows_evaluation_only_change(tmp_path: Path) -> None:
    dataset = _tiny_dataset(tmp_path)
    execution = BasicCleaner([{"quality.blur_check": {"min_score": 100.0}}]).compile()
    result = execution.run(dataset)

    rerun_result = execution.rerun(
        result,
        operators=[{"quality.blur_check": {"min_score": 999999.0, "action": "review"}}],
    )

    assert rerun_result.status() == "completed"
```

- [ ] **Step 4: Implement evaluation-only rerun**

Reuse completed parameter artifacts and rerun only evaluation nodes and merge. Reject rerun when parameter computer config or graph changes.

- [ ] **Step 5: Integrate semantic artifacts with manifest validation**

Update `src/image_gallery/operators/computers/semantic.py` and runtime artifact handling so semantic embeddings, faiss index, and semantic duplicate relation each have manifest records. Keep deterministic provider tests from `tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py` passing.

- [ ] **Step 6: Run Task 8 tests**

Run: `.venv/bin/python -m pytest tests/integration/cleaning/test_cleaner_runtime_resume.py tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py -q`  
Expected: PASS.

- [ ] **Step 7: Commit Task 8**

```bash
git add src/image_gallery/cleaning/runtime.py \
  src/image_gallery/cleaning/scheduler.py \
  src/image_gallery/operators/computers/semantic.py \
  src/image_gallery/operators/computers/duplicate.py \
  tests/integration/cleaning/test_cleaner_runtime_resume.py \
  tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py
git commit -m "feat: support cleaner resume and rerun"
```

---

### Task 9: TOML Templates, Notebook Helpers, and User-Facing Examples

**Files:**
- Modify: `notebooks/_helpers/cleaning_configs.py`
- Modify: `notebooks/operators_builtin_test.ipynb`
- Modify: `notebooks/cleaning_v3_sample_1000_test.ipynb`
- Create: `examples/cleaning_runtime.toml`
- Test: `tests/unit/notebooks/test_cleaning_configs_helper.py`
- Test: `tests/integration/cleaning/test_cleaner_runtime_toml.py`

**Interfaces:**
- Consumes: `BasicCleaner.from_toml`, selector inputs, `CleanerResult`.
- Produces: Notebook helper configs using `ALL`, `QUALITY`, and `DUPLICATE`.
- Produces: TOML template example without secrets.

- [ ] **Step 1: Write failing TOML integration test**

Add to `tests/integration/cleaning/test_cleaner_runtime_toml.py`:

```python
from pathlib import Path

from image_gallery.cleaning import BasicCleaner


def test_from_toml_run_matches_python_api(tmp_path: Path) -> None:
    dataset = _tiny_dataset(tmp_path)
    config_path = tmp_path / "cleaning.toml"
    config_path.write_text(
        """
[cleaner]
operators = ["format.decode_check"]
""".strip(),
        encoding="utf-8",
    )

    result = BasicCleaner.from_toml(config_path).run(dataset)

    assert result.status() == "completed"
```

- [ ] **Step 2: Implement `BasicCleaner.from_toml`, `from_config`, and template export**

Modify `src/image_gallery/cleaning/basic.py` to add:

```python
@classmethod
def from_config(cls, config: CleanerConfig) -> "BasicCleaner":
    return cls(
        operators=config.operators,
        node_policy=config.node_policy,
        operator_policies=config.operator_policies,
        operator_config_overrides=config.operator_configs,
    )

@classmethod
def from_toml(cls, path: str | Path) -> "BasicCleaner":
    return cls.from_config(CleanerConfig.from_toml(path))

@classmethod
def export_config_template(cls, path: str | Path, operators: object) -> Path:
    template = build_cleaner_toml_template(operators)
    output_path = Path(path)
    output_path.write_text(template, encoding="utf-8")
    return output_path
```

- [ ] **Step 3: Add `examples/cleaning_runtime.toml`**

Create a non-secret example:

```toml
[cleaner]
operators = ["QUALITY", "DUPLICATE"]

[node_policy.batch]
size = 128

[node_policy.failure]
fail_fast = false
max_errors = 100

[[operator]]
name = "quality.blur_check"
min_score = 100.0
action = "review"
```

- [ ] **Step 4: Update notebook helpers**

Update `notebooks/_helpers/cleaning_configs.py` so helpers return TOML-compatible config examples and result-based API snippets. Keep helper tests passing.

- [ ] **Step 5: Update notebooks**

Update notebooks to use:

```python
result = BasicCleaner(configs).run(dataset, progress="auto")
result.preview_html(PREVIEW_DIR / "quality_blur.html", operator_name="quality.blur_check")
result.export_table("parameter", RUN_OUTPUT_DIR / "parameter_table.parquet")
```

Do not read internal cache paths from notebooks.

- [ ] **Step 6: Run Task 9 tests**

Run: `.venv/bin/python -m pytest tests/unit/notebooks/test_cleaning_configs_helper.py tests/integration/cleaning/test_cleaner_runtime_toml.py -q`  
Expected: PASS.

- [ ] **Step 7: Commit Task 9**

```bash
git add src/image_gallery/cleaning/basic.py \
  notebooks/_helpers/cleaning_configs.py \
  notebooks/operators_builtin_test.ipynb \
  notebooks/cleaning_v3_sample_1000_test.ipynb \
  examples/cleaning_runtime.toml \
  tests/unit/notebooks/test_cleaning_configs_helper.py \
  tests/integration/cleaning/test_cleaner_runtime_toml.py
git commit -m "docs: add cleaner runtime notebook examples"
```

---

### Task 10: Verification Gate and Compatibility Cleanup

**Files:**
- Modify: `tests/integration/cleaning/test_basic_cleaner_builtin_run.py`
- Modify: `tests/integration/cleaning/test_basic_cleaner_export.py`
- Modify: `tests/integration/cleaning/test_basic_cleaner_minimal_run.py`
- Modify: `tests/integration/cleaning/test_basic_cleaner_rerun.py`
- Modify: `src/image_gallery/cleaning/__init__.py`
- Test: existing cleaning, operators, notebooks, integration subsets.

**Interfaces:**
- Consumes: all public APIs from Tasks 1-9.
- Produces: final verified runtime migration with stale compatibility removed.

- [ ] **Step 1: Update existing tests to the new result lifecycle**

Replace old patterns:

```python
cleaner = BasicCleaner(configs)
cleaner.run(dataset, output_dir=tmp_path / "cleaning")
full = cleaner.export("full", str(tmp_path / "full.parquet"))
```

with:

```python
result = BasicCleaner(configs).run(dataset)
full = result.export("full", tmp_path / "full.parquet")
```

- [ ] **Step 2: Remove stale compatibility from `BasicCleaner`**

Remove direct result-reader methods from `BasicCleaner` if they only proxy old internal state. Keep only builder methods and shortcut `run()`. Any remaining `BasicCleaner.preview()` / `state()` compatibility must either be intentionally supported or removed with tests updated.

- [ ] **Step 3: Run default fast verification**

Run:

```bash
.venv/bin/python -m pytest tests/unit/cleaning tests/unit/operators -q
.venv/bin/python -m pytest tests/integration/cleaning -q
.venv/bin/python -m pytest tests/unit/notebooks -q
.venv/bin/python -m ruff check src tests
.venv/bin/python -m mypy src/image_gallery
```

Expected: all commands PASS.

- [ ] **Step 4: Run semantic artifact verification**

Run:

```bash
PYTHONPATH=src:. .venv/bin/python -m pytest tests/integration/cleaning/test_basic_cleaner_semantic_duplicate.py -q
```

Expected: PASS and semantic embedding, index, and relation manifests exist through exported manifest/debug bundle checks.

- [ ] **Step 5: Run notebook smoke when environment supports it**

Run:

```bash
.venv/bin/python -m jupyter nbconvert --to notebook --execute notebooks/cleaning_v3_sample_1000_test.ipynb --inplace
```

Expected: PASS. If notebook dependencies or MinIO credentials are unavailable, record the exact failure and run the closest pytest substitute.

- [ ] **Step 6: Commit Task 10**

```bash
git add src/image_gallery/cleaning \
  tests/unit/cleaning \
  tests/unit/operators \
  tests/unit/notebooks \
  tests/integration/cleaning \
  notebooks/cleaning_v3_sample_1000_test.ipynb \
  notebooks/operators_builtin_test.ipynb
git commit -m "test: verify cleaner runtime migration"
```

---

## Final Verification Checklist

- [ ] `BasicCleaner(operator_configs).compile()` returns `CleanerExecution`.
- [ ] `BasicCleaner(operator_configs).run(dataset)` returns `CleanerResult`.
- [ ] Process artifacts default to system cache and are not exposed as public paths.
- [ ] `CleanerResult` can export clean, dropped, full, parameter table, evaluation table, manifests, relations, preview HTML, and debug bundle.
- [ ] StateGraph includes parameter, evaluation, and merge nodes.
- [ ] SQLite stores run, node, stage, batch, artifact, and event state.
- [ ] Resume validates dataset fingerprint, plan hash, parameter config hash, policy hash, artifact manifest, and sample rule.
- [ ] Rerun allows evaluation-only changes and rejects parameter graph/config/policy changes.
- [ ] Built-in preview policies exist for all current built-in operators.
- [ ] TOML, selectors, direct spec input, progress events, label/tags, dry run, template export, explain, and sample run are tested.
- [ ] Fast verification commands pass.
- [ ] Slow semantic duplicate artifact test passes or the final report explains why it could not run.
- [ ] Notebook smoke passes or the final report explains why it could not run.
