# Cleaning Planner/Scheduler Refactor Design

## 背景

当前清洗 v3 已经具备基本闭环：`BasicCleaner` 解析用户传入的逻辑算子配置，收集 `OperatorSpec.required_parameters`，调用 `ParameterComputer` 生成 `parameter_table`，再由逻辑算子 evaluator 生成 `evaluation_table` 和最终导出视图。

随着去重、CLIP、YOLO、聚类、相似图关系等算子加入，`BasicCleaner` 不应继续承担所有执行细节。清洗平台需要把“配置编译”“参数计算调度”“逻辑算子评估”拆开，让后续复杂算子可以通过声明依赖接入，而不是在 `BasicCleaner` 中增加业务分支。

本设计允许破坏式内部重构，不保留旧内部接口兼容；用户侧算子配置格式保持不变。

## 目标

1. 引入 `Cleaner.compile()`，把用户配置提前编译为可执行计划。
2. 引入 `Cleaner.plan()`，用于查看静态执行顺序。
3. 从 `BasicCleaner` 中拆出 `CleaningRunPlanner`、`ParameterScheduler` 和 `OperatorEvaluator`。
4. 用参数依赖 DAG 决定 `ParameterComputer` 执行顺序。
5. 把现有 `ComputeStage` 改为更准确的 `ExecutionMode`。
6. 明确 `ParameterComputer` 是最小调度单元，避免 computer 变成新的混合职责对象。

## 非目标

1. 不改变用户侧 operator 配置格式。
2. 不实现 CLIP、YOLO、近似去重或模型推理。
3. 不实现完整 DAG runtime、并发执行、节点重试或局部恢复。
4. 不拆出独立 `ArtifactStore` 或 `StateManager` 类；现有 tables/state 写入函数第一阶段继续复用。
5. 不扩大 `rerun()` 语义；第一阶段仍保持 evaluation-only。
6. 不实现分块 image batch；`PER_IMAGE` 第一阶段继续共享完整 `ImageBatch`。

## 核心原则

逻辑算子属于语义层，`ParameterComputer` DAG 属于执行层。

`OperatorSpec.required_parameters` 只声明逻辑评估最终需要的参数，不描述这些参数如何生产。参数生产路径由注册到 `OperatorRegistry` 的 `ParameterComputer.produced_parameters` 和 `ParameterComputer.required_parameters` 反向推导。

`OperatorRegistry` 是依赖事实来源，`CleaningRunPlanner` 是依赖推导器，`ParameterScheduler` 是计划执行器，`BasicCleaner` 是用户侧门面。

## ExecutionMode

把现有 `ComputeStage` 改为 `ExecutionMode`：

```python
class ExecutionMode(str, Enum):
    PER_IMAGE = "per_image"
    TABLE = "table"
    DATASET_AGGREGATE = "dataset_aggregate"
```

`ExecutionMode` 不决定执行顺序。执行顺序由参数依赖 DAG 拓扑排序决定；`ExecutionMode` 只决定 Scheduler 如何执行当前 step。

### PER_IMAGE

单张图片可独立计算的参数。Scheduler 负责准备共享 `ImageBatch`，computer 从 batch item 中读取图片字节、解码结果或行上下文。

适用参数示例：

- `decode_ok`
- `width`
- `height`
- `content_hash`
- `blur_score`
- `brightness_score`
- `clip_embedding_ref`
- `yolo_detection_ref`

### TABLE

不读图片，只基于已有 `parameter_table` 派生参数。

适用参数示例：

- `aspect_ratio`
- `megapixels`
- 基于已有列派生的规则特征

### DATASET_AGGREGATE

需要完整运行集合或多图关系才能计算的参数。它不负责图片读取或单图模型推理，只消费已有 per-image/table 参数并生成分组、关系、聚类或全局统计。

适用参数示例：

- `exact_duplicate_group_id`
- `near_duplicate_group_id`
- `semantic_duplicate_group_id`
- `cluster_id`
- `outlier_score`

硬规则：如果一个 computer 的每行输出只由该行图片和该行已有参数决定，它不允许标记为 `DATASET_AGGREGATE`。

## ParameterComputer 调度约束

`ParameterComputer` 是最小调度单元：

```python
class ParameterComputer:
    name: str
    execution_mode: ExecutionMode
    produced_parameters: frozenset[str]
    required_parameters: frozenset[str] = frozenset()
```

一个 computer 的所有输出参数必须共享同一组 `required_parameters` 和同一个 `execution_mode`。如果同一段业务逻辑需要在不同依赖阶段产出不同参数，应拆成多个 computer，并通过内部 helper 复用实现。

第一阶段不支持同一个 computer 在同一个 plan 中执行多次。`requested_parameters` 只用于让一个原子 computer 在本次运行中少产一些列，不用于把一个 computer 拆成多个执行阶段。

示例：

```text
ImageHashComputer(PER_IMAGE)
  produces: content_hash

DuplicateGroupComputer(DATASET_AGGREGATE)
  requires: content_hash
  produces: exact_duplicate_group_id, exact_duplicate_count
```

语义去重也应拆成两段：

```text
ClipEmbeddingComputer(PER_IMAGE)
  produces: clip_embedding_ref

ClipDuplicateGroupComputer(DATASET_AGGREGATE)
  requires: clip_embedding_ref
  produces: semantic_duplicate_group_id, semantic_duplicate_count
```

## Registry 约束

`OperatorRegistry` 需要维护参数生产索引：

```text
parameter_name -> producer computer
```

第一版禁止多个 producer 生产同一个 parameter。注册重复 producer 时直接报错，避免 Planner 遇到歧义。后续如果需要多个 provider，可再引入 priority 或显式配置选择。

Registry 负责保存事实：

1. 有哪些 `OperatorSpec`。
2. 有哪些 `ParameterComputer`。
3. 哪个参数由哪个 computer 生产。
4. 是否存在重复 producer。

Planner 负责基于这些事实推导执行计划。

## Compile 生命周期

`Cleaner` 抽象基类新增：

```python
def compile(self) -> "Cleaner": ...
def plan(self) -> pd.DataFrame: ...
```

`BasicCleaner.compile()` 行为：

1. 不读取 dataset。
2. 不计算参数。
3. 不写任何产物。
4. 只依赖 operator configs 和 registry。
5. 编译并缓存 `CompiledCleaningPlan`。
6. 返回 `self`。

`BasicCleaner.plan()` 行为：

1. 如果尚未 compile，则自动 compile。
2. 返回计划 DataFrame，方便 Notebook 展示。

计划 DataFrame 建议列：

- `step_index`
- `computer_name`
- `execution_mode`
- `requested_parameters`
- `required_parameters`
- `produced_parameters`
- `upstream_computers`

`BasicCleaner.run()` 行为：

1. 如果尚未 compile，则自动 compile。
2. 创建 run context 和初始 tables。
3. 交给 `ParameterScheduler` 执行已编译计划。
4. 交给 `OperatorEvaluator` 执行逻辑算子评估。
5. 聚合 `final_action`。
6. 写出 tables、manifest、relations 和 state。

`BasicCleaner.config()` 行为：

1. 更新 operator configs。
2. 标记已有 run 中相关 operator state 为 stale。
3. 清空 `_compiled_plan`，使下一次 `plan()` 或 `run()` 重新 compile。

`BasicCleaner.rerun()` 第一阶段保持 evaluation-only，不重新执行 parameter computers。

## 计划对象

```python
@dataclass(frozen=True)
class ParameterExecutionStep:
    computer_name: str
    requested_parameters: frozenset[str]
    required_parameters: frozenset[str]
    produced_parameters: frozenset[str]
    execution_mode: ExecutionMode
    upstream_computer_names: tuple[str, ...]
```

```python
@dataclass(frozen=True)
class ParameterExecutionPlan:
    steps: tuple[ParameterExecutionStep, ...]
```

```python
@dataclass(frozen=True)
class CompiledCleaningPlan:
    resolved_operator_runs: tuple[ResolvedOperatorRun, ...]
    parameter_plan: ParameterExecutionPlan
    operator_config_hashes: dict[str, str]
```

第一版 Scheduler 只消费拓扑排序后的线性 `steps`。`upstream_computer_names` 保留 DAG 信息，用于调试、`plan()` 展示和未来扩展。

## Planner 设计

`CleaningRunPlanner` 输入：

- `ParsedOperatorConfig`
- `OperatorRegistry`

`CleaningRunPlanner` 输出：

- `CompiledCleaningPlan`

执行流程：

1. 根据 operator configs resolve `OperatorSpec`。
2. 合并 `OperatorSpec.default_config` 和用户配置，生成 `ResolvedOperatorRun`。
3. 收集所有逻辑算子的最终 `required_parameters`。
4. 通过 registry 的 parameter producer index 找到 producer computer。
5. 递归展开每个 producer 的 `required_parameters`。
6. 构建 computer DAG。
7. 检查缺失 producer。
8. 检查依赖环。
9. 拓扑排序。
10. 生成 `ParameterExecutionStep` 列表。

拓扑排序的顺序由依赖决定。对于同一层没有依赖关系的 computers，可使用稳定排序保证计划可预测，例如按 `execution_mode` 再按 `computer_name` 排序。这个排序只是 tie-breaker，不表达硬阶段顺序。

## Scheduler 设计

`ParameterScheduler` 输入：

- `ParameterExecutionPlan`
- `CleanerRunContext`
- 当前 `CleaningTables`
- `OperatorRegistry`

`ParameterScheduler` 输出：

- 更新后的 `CleaningTables`
- `artifact_paths`
- `relation_paths`

执行职责：

1. 如果 plan 中存在 `PER_IMAGE` step，则构建一次共享 `ImageBatch`。
2. 按 `plan.steps` 顺序执行。
3. 根据 step 的 `execution_mode` 决定是否传入 `image_batch`。
4. 用 step 的 `requested_parameters` 约束本次需要生产的参数。
5. 合并 `parameter_updates` 到 `parameter_table`。
6. 合并 `parameter_manifest`。
7. 写出 relation tables 并收集 relation paths。
8. 收集 artifact refs。

第一阶段保留当前完整 `ImageBatch` 行为，不做分块和并发。

## Evaluator 设计

`OperatorEvaluator` 输入：

- `ResolvedOperatorRun`
- 当前 `CleaningTables`

输出：

- 更新后的 `CleaningTables`
- `OperatorRunState`

执行职责：

1. 调用 `OperatorSpec.evaluate()`。
2. 验证 evaluator 输出列。
3. 更新 `evaluation_table`。
4. 更新 `operator_outputs`。
5. 返回 operator state。

Evaluator 不读取图片，不执行 parameter computers，不写磁盘。

## BasicCleaner run 流程

```text
BasicCleaner.run(dataset)
  -> compile if needed
  -> create_run_context()
  -> initialize_parameter_table()
  -> initialize_evaluation_table()
  -> ParameterScheduler.run(compiled_plan.parameter_plan)
  -> for each resolved operator:
       OperatorEvaluator.evaluate()
  -> apply_final_action()
  -> build CleanerRunState
  -> write_tables()
  -> save state.json
```

`BasicCleaner` 不再直接展开 parameter dependencies，也不直接循环 execution mode。

## 错误处理

Planner 阶段应尽早失败：

1. 未知 operator：沿用 `UnknownOperatorError`。
2. 缺失 parameter producer：抛出清晰错误，包含缺失参数名。
3. 重复 parameter producer：注册阶段或 compile 阶段抛出清晰错误。
4. 参数依赖环：compile 阶段抛出清晰错误，包含环上的 computer 名称。

Scheduler 阶段处理执行错误：

1. `PER_IMAGE` 图片读取失败仍按当前行为记录到 image batch item，不阻断整个 run。
2. computer 缺少必须输入时直接失败。
3. computer 输出缺少 step 请求参数时直接失败。

## 测试策略

### Planner 单元测试

1. 从 `duplicate.exact_duplicate_check` 展开出 `ImageHashComputer -> DuplicateGroupComputer`。
2. 从多个 quality operator 展开出同一个 `ImageQualityComputer`，且 `requested_parameters` 只包含本次需要的列。
3. 缺失 producer 时失败。
4. 重复 producer 注册时失败。
5. 构造循环依赖时失败。
6. `plan()` 返回稳定顺序和可读 DataFrame。

### Scheduler 单元测试

1. 有多个 `PER_IMAGE` step 时只构建一次共享 image batch。
2. `TABLE` step 不接收 image batch。
3. `DATASET_AGGREGATE` step 在上游参数写入后执行。
4. parameter manifest、artifact refs、relation paths 正确合并。

### BasicCleaner 集成测试

1. 现有第一批内置算子通过 `run()` 自动 compile 后完整运行。
2. 显式 `compile().run(dataset)` 与直接 `run(dataset)` 产物一致。
3. `plan()` 不读取图片、不写输出目录。
4. `config()` 后 plan 失效并可重新 compile。
5. `rerun()` 保持 evaluation-only。

### 回归验证

运行范围：

```bash
.venv/bin/python -m pytest tests/unit/operators tests/unit/cleaning tests/integration/cleaning -q
.venv/bin/python -m ruff check src/image_gallery tests
.venv/bin/python -m mypy src/image_gallery
```

如果 mypy 覆盖范围中存在既有无关问题，应记录实际失败点，不在本重构中顺手修复无关代码。

## 成功标准

1. 用户侧 `BasicCleaner([{operator_name: config}, ...])` 配置格式不变。
2. `BasicCleaner.compile()` 可用并返回 `self`。
3. `BasicCleaner.plan()` 可展示拓扑排序后的 computer 级执行计划。
4. `BasicCleaner.run()` 不再直接做 parameter dependency 展开。
5. `ParameterComputer` 使用 `execution_mode`，不再使用 `ComputeStage.stage`。
6. 去重链路通过依赖图表达为 per-image hash 后 dataset aggregate 分组。
7. 第一批内置算子测试和清洗集成测试通过。
