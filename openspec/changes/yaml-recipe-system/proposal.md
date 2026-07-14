## Why

TOML 配置面向开发者，但非技术用户更需要声明式 YAML 配方：用区间语法 `"[0, 0.3]"` 表达 drop/review 阈值，按算子短名组合清洗规则。同时，运行产物存储模式硬编码为文件系统，测试中无法使用内存模式避免 IO。ActionRange、MetricSpec、CleanerRecipe 和 RunStore 四个子系统构成面向用户的完整配方体验。

## What Changes

- 新增 `ActionRange` 类：解析数学区间语法（如 `"[0, 0.3]"`、`"(0.3, 0.6]"`），支持 `contains()` 判断
- 新增 `MetricSpec` 数据类：描述每个算子指标的类型（absolute/relative/categorical）、范围和方向
- 新增 `CleanerRecipe.from_yaml()` 和 `BasicCleaner.from_recipe()`：从 YAML 加载配方，编译为 selector 列表
- 新增双级动作评估：基于 ActionRange 区间的 drop > review > keep 优先级评估
- 新增 `RunStore` 抽象：memory / temporary / disk 三种存储模式
- 新增依赖：`pyyaml`

## Capabilities

### New Capabilities

_无新增 capability（所有能力已在 cleaning-config 和 cleaning-runtime spec 中定义为 PLANNED）_

### Modified Capabilities

- `cleaning-config`: 实现 ActionRange 区间解析、MetricSpec 阈值元数据、YAML Recipe 系统、双级动作评估（均为 PLANNED → 实现）
- `cleaning-runtime`: 实现 RunStore 存储模式（PLANNED → 实现）

## Impact

- **代码**: 新增 `cleaning/recipe.py`（CleanerRecipe + from_yaml）、`cleaning/action_range.py`（ActionRange）、`operators/metric_spec.py`（MetricSpec）、`cleaning/run_store.py`（RunStore 抽象 + 三个实现）
- **依赖**: 新增 `pyyaml` 到 `pyproject.toml`
- **测试**: 新增 `tests/unit/cleaning/test_recipe.py`、`tests/unit/cleaning/test_action_range.py`、`tests/unit/operators/test_metric_spec.py`、`tests/unit/cleaning/test_run_store.py`
- **集成**: `BasicCleaner` 新增 `from_recipe()` 工厂方法，`CleaningRuntime` 接受 `RunStore` 参数
