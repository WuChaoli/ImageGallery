# Cleaner Runtime StateGraph Design

## 背景

当前清洗 v3 已经拆出 `CleaningRunPlanner`、`ParameterScheduler` 和 `OperatorEvaluator`，但运行模型仍然是 `BasicCleaner.run()` 一次性在内存中完成参数计算和评估，最后把 `parameter_table.parquet`、`evaluation_table.parquet`、`parameter_manifest.json`、`state.json` 等过程产物写入用户指定目录。

随着语义去重、感知哈希、轻量质量算子和后续全局类算子增加，现有运行时有几个明显问题：

1. `BasicCleaner` 同时承担 builder、execution 和 result reader 职责。
2. 参数计算顺序只覆盖 parameter plan，evaluation 和 merge 没有进入统一执行图。
3. `state.json` 是完成后的摘要，不是可恢复运行的事实来源。
4. 过程产物默认暴露在用户目录，用户容易依赖内部文件布局。
5. 没有统一 checkpoint、retry、resume 和 artifact manifest 语义。

本设计允许破坏式重构，不保留旧内部接口兼容。用户侧 `list[{operator_name: config}]` 的算子配置结构继续保留。

## 目标

1. 把 Cleaner 生命周期拆成 builder、execution 和 result 三段。
2. 引入阶段级 `CleaningStateGraph`，用依赖 DAG 描述 parameter、evaluation 和 merge 节点。
3. 使用 SQLite 作为运行状态事实来源，支持 checkpoint、retry、resume 和 rerun。
4. 过程产物默认写入系统缓存目录，不直接暴露缓存路径。
5. 通过 `CleanerResult` 提供只读查询和显式导出 API。
6. 为每个逻辑算子定义 `PreviewPolicy`，作为该算子最常用的预览结构。
7. 保留 `BasicCleaner.run(dataset)` 快捷入口，但它只代理 `compile().run(dataset)` 并返回 `CleanerResult`。

## 非目标

1. 不实现跨 run artifact 复用。第一版 cache 只服务当前 run 的 checkpoint 和结果 backing files。
2. 不暴露内部缓存目录作为稳定 API。
3. 不在 `OperatorSpec` 中定义默认 `NodePolicy`，避免共享 parameter node 的策略冲突。
4. 不引入分布式调度器或服务端 API。
5. 不把每张图片或每个 batch 放入主图；batch 是节点内部 checkpoint。

## API 生命周期

`BasicCleaner` 是 builder，只负责加载逻辑算子、注册表、provider 和运行策略默认值。

```python
cleaner = BasicCleaner(
    operators=[
        {"quality.blur_check": {"threshold": 100.0, "action": "drop"}},
        {"duplicate.semantic_duplicate_check": {"threshold": 0.9, "action": "drop"}},
    ],
    node_policy=NodePolicy(...),
    operator_policies={
        "duplicate.semantic_duplicate_check": NodePolicy(...),
    },
    registry=None,
    providers=None,
)
```

`compile()` 返回不可变 `CleanerExecution`：

```python
execution = cleaner.compile()
result = execution.run(dataset)
```

`BasicCleaner.run(dataset)` 保留为 Notebook 和脚本快捷入口：

```python
result = BasicCleaner(operators).run(dataset)
```

它等价于：

```python
result = BasicCleaner(operators).compile().run(dataset)
```

`CleanerExecution` 负责运行控制：

```python
result = execution.run(dataset)
resumed = execution.resume(dataset=dataset, run_id=result.run_id)
resumed = execution.resume(dataset=dataset, result=result)
rerun_result = execution.rerun(result, operators=[...])
```

`dataset` 在 `resume()` 中仍然必传。运行时用当前 `dataset.fingerprint()` 校验历史 run，不把 Dataset 或 Storage secret 序列化进 SQLite。

`CleanerResult` 负责结果读取和显式导出：

```python
result.status()
result.summary()
result.state()
result.result("quality.blur_check")
result.preview(operator_name="quality.blur_check", actions=["drop", "review"])
result.preview_html("blur.html", operator_name="quality.blur_check", actions="drop")
result.export("clean", "clean.parquet")
result.export_table("parameter", "parameter_table.parquet")
result.export_manifest("artifacts", "artifacts.json")
result.export_relations("semantic_duplicate_pairs", "pairs.parquet")
result.export_debug_bundle("debug-cleaning-run.zip")
result.cleanup()
```

`CleanerResult` 不公开 `work_dir`、`parameter_table_path`、`evaluation_table_path` 或 artifact 目录路径。调试和 Notebook 验证通过只读导出 API 复制过程产物。

## CleaningStateGraph

`CleaningStateGraph` 是阶段级依赖 DAG。图结构不由用户传入逻辑算子的顺序决定，而由 parameter、artifact、relation 和 evaluation 的依赖决定。用户顺序只作为展示顺序和同层 tie-breaker。

排序规则：

1. 必须先满足 `required_parameters`、`required_artifacts` 和 `required_relations`。
2. 同层节点按 `node_type` 和 `execution_mode` 稳定排序。
3. 仍然并列时，用用户配置顺序作为 tie-breaker。

主图节点类型：

```text
parameter
evaluation
merge
```

节点字段：

```text
node_id
node_type
operator_name
computer_name
stage_name
execution_mode
required_parameters
produced_parameters
required_artifacts
produced_artifacts
required_relations
produced_relations
config_hash
policy_hash
checkpoint_strategy
cache_policy
artifact_contract
```

节点颗粒度：

1. 默认一个 `ParameterComputer` 是一个 parameter node。
2. 如果 computer 声明 `stages`，每个 stage 是一个 parameter node。
3. 每个 `OperatorSpec` evaluator 是一个 evaluation node。
4. `final_action` 聚合是固定 merge node，依赖所有 evaluation nodes。
5. batch 是 node 内部 checkpoint，不进入主图。

示例：

```text
parameter.semantic_embedding.extract
  -> parameter.semantic_index.build
  -> parameter.semantic_duplicate_group.find
  -> evaluation.duplicate.semantic_duplicate_check
  -> merge.final_action

parameter.image_quality
  -> evaluation.quality.blur_check
  -> merge.final_action
```

## OperatorSpec PreviewPolicy

`OperatorSpec` 增加 `preview_policy`，用于描述该逻辑算子的默认预览结构。

```python
OperatorSpec(
    name="duplicate.semantic_duplicate_check",
    ...,
    preview_policy=PreviewPolicy(
        default_actions=["drop", "review"],
        caption_columns=[
            "semantic_duplicate_score",
            "semantic_duplicate_nearest_image_id",
            "semantic_duplicate_reason",
        ],
        groupby="semantic_duplicate_group_id",
        include_group_context=True,
        sort_by=["semantic_duplicate_group_id", "semantic_duplicate_score"],
        ascending=[True, False],
        max_items_per_group=20,
    ),
)
```

`PreviewPolicy` 是展示建议，不影响评估逻辑和清洗结果。用户显式传入的 `preview()` 或 `preview_html()` 参数覆盖 policy；policy 只补默认值。

建议字段：

```python
PreviewPolicy(
    default_actions=None,
    caption_columns=None,
    groupby=None,
    include_group_context=False,
    sort_by=None,
    ascending=True,
    max_rows=200,
    max_groups=50,
    max_items_per_group=20,
    thumbnail_size=320,
    columns_per_row=6,
)
```

调用规则：

```python
result.preview_html("overall.html")
```

不传 `operator_name` 时，预览整体 `final_action` 视图，使用全局默认 preview policy。

```python
result.preview_html("semantic.html", operator_name="duplicate.semantic_duplicate_check")
```

传 `operator_name` 时，使用该算子的 `OperatorSpec.preview_policy`。

```python
result.preview_html(
    "semantic_all.html",
    operator_name="duplicate.semantic_duplicate_check",
    actions="full",
    include_group_context=False,
)
```

用户显式参数覆盖默认 policy。

## Action 筛选

`preview()` 和 `preview_html()` 使用 `actions` 作为统一动作筛选参数。

```python
result.preview_html("drop_review.html", actions=["drop", "review"])
result.preview_html("semantic_drop.html", operator_name="duplicate.semantic_duplicate_check", actions="drop")
```

语义：

1. `actions=None`：使用 preview policy 的默认动作；如果没有默认动作，展示全部。
2. `actions="drop"`：只展示 `drop`。
3. `actions=["drop", "review"]`：展示多个动作。
4. `actions="full"`：特殊别名，展示完整结果，不按 action 过滤。
5. `full` 不能和其他动作混用。
6. 整体预览按 `final_action` 筛选。
7. 单逻辑算子预览按该算子的 action column 筛选。
8. 未知 action 直接报错。

标准动作集合：

```text
clean
drop
review
full
```

`clean` 表示该视图下保留的样本；整体视图中可映射为 `final_action == "keep"`，单算子视图中可映射为该算子的 keep/clean action。

## NodePolicy

业务配置和运行策略分开。`operators` 只保存算子业务配置；`node_policy` 和 `operator_policies` 保存运行策略。

```python
NodePolicy(
    batch=BatchPolicy(size=128),
    checkpoint=CheckpointPolicy(enabled=True, strategy="auto"),
    cache=CachePolicy(scope="system", reuse="run", cleanup="on_success"),
    failure=FailurePolicy(
        fail_fast=False,
        max_errors=None,
        bad_image_action="mark_failed",
        retry=RetryPolicy(
            max_attempts=1,
            backoff_seconds=0.0,
            retry_on=("io_error", "temporary_error", "artifact_commit_error"),
        ),
    ),
    resources=ResourcePolicy(max_workers=1, device="auto"),
    artifacts=ArtifactPolicy(retain_intermediate=False, write_debug_manifest=True),
)
```

`OperatorSpec` 第一版不定义默认 `NodePolicy`。默认策略来源是：

```text
系统默认 policy
  < ParameterComputer / stage 默认 policy
  < BasicCleaner(node_policy=...)
  < BasicCleaner(operator_policies={...})
```

`ParameterComputer` 或 stage 还需要声明 capability，例如支持的 checkpoint strategy、是否支持 batch、是否允许 retry。用户配置和 capability 冲突时，compile 阶段直接失败。

## Retry、Resume 与 Rerun

`RetryPolicy` 是同一次运行内的失败重试。`resume()` 是进程中断或 run 停止后的恢复。

失败分三层：

1. image-level failure：单张图片读取或解码失败，记录 item status，继续同 batch。
2. batch/stage-level failure：batch 或 stage 失败后，根据 `RetryPolicy` 重试。
3. node-level failure：重试耗尽后，根据 `fail_fast` 和 `max_errors` 决定 run 是否停止。

`resume()` 校验规则：

1. `dataset_fingerprint` 必须一致。
2. `plan_hash` 必须一致。
3. parameter node 的 `config_hash` 和 `policy_hash` 必须一致。
4. 已完成节点的 artifact manifest 必须存在且校验通过。
5. 不一致时拒绝 resume，提示用户重新 run 或使用 evaluation-only `rerun()`。

`rerun()` 语义：

1. 只允许 evaluation-only 业务配置变化复用 parameter artifacts。
2. 如果变化影响 parameter graph、parameter config 或 node policy，拒绝 `rerun()`。
3. `rerun()` 默认产出新的 result version，不覆盖旧 result。
4. 显式 `overwrite=True` 时才允许覆盖旧 result version。

## SQLite 状态存储

SQLite 是运行状态事实来源。`state.json` 仅是用户可读摘要，不参与 resume 判断。

第一版 schema：

```text
cleaning_run
  run_id
  cleaner_type
  status
  dataset_fingerprint
  plan_hash
  cache_root
  started_at
  updated_at
  finished_at

graph_node
  run_id
  node_id
  node_type
  status
  config_hash
  policy_hash
  checkpoint_strategy
  started_at
  updated_at
  finished_at
  error_message

stage_run
  run_id
  node_id
  stage_name
  status
  attempt_count
  artifact_id
  started_at
  updated_at
  finished_at
  error_message

batch_run
  run_id
  node_id
  batch_id
  status
  input_start
  input_end
  row_count
  error_count
  attempt_count
  artifact_id
  started_at
  updated_at
  finished_at
  error_message

artifact
  run_id
  artifact_id
  artifact_type
  owner_node_id
  uri
  manifest_uri
  status
  row_count
  checksum
  created_at

run_event
  run_id
  event_id
  event_type
  node_id
  batch_id
  message
  payload_json
  created_at
```

SQLite 不保存图片二进制、缩略图二进制、大规模 DataFrame 内容、MinIO secret key 或访问 token。

## Cache 与 Artifact

过程产物默认写入系统缓存目录：

```text
~/.cache/image_gallery/cleaning/runs/{run_id}/
  run_state.sqlite
  state.json
  graph.json
  manifests/
    execution_plan.json
    artifacts.json
    parameter_manifest.json
    operator_outputs.json
  tables/
    parameter_table.parquet
    evaluation_table.parquet
  relations/
  artifacts/
    committed/
    tmp/
  cache/
    steps/
    batches/
    stages/
```

`CachePolicy(scope="system", reuse="run")` 表示只复用当前 run 的 checkpoint，不跨 run 复用 embedding、index 或 hash artifact。

正式提交流程：

```text
write tmp artifact
  -> validate schema / row count / checksum
  -> write artifact manifest
  -> promote to committed artifact
  -> update SQLite artifact status
  -> update node / batch / stage status
```

只有 SQLite 状态和 artifact manifest 都完成时，节点才视为 completed。

## Result 导出

普通用户不会看到内部缓存路径。所有外部产物都通过 `CleanerResult` 显式导出。

```python
result.export("clean", "clean.parquet")
result.export("dropped", "dropped.parquet")
result.export("full", "full.parquet")
result.export_table("parameter", "parameter_table.parquet")
result.export_table("evaluation", "evaluation_table.parquet")
result.export_manifest("execution_plan", "execution_plan.json")
result.export_manifest("artifacts", "artifacts.json")
result.export_relations("semantic_duplicate_pairs", "pairs.parquet")
result.export_debug_bundle("debug-cleaning-run.zip")
```

`cleanup()` 清理内部缓存后，result 进入 `cleaned` 状态。已导出的用户文件不受影响；未导出的内容之后不可再导出。

## 错误处理

1. compile 阶段发现未知算子、缺少 producer、依赖环、policy capability 冲突时直接失败。
2. run 阶段节点失败会写入 SQLite `run_event` 和节点状态。
3. retry 耗尽后，如果 `fail_fast=True`，run 立即失败。
4. `fail_fast=False` 时，允许可标记失败的 image-level 错误继续；node-level 不可恢复错误仍会停止 run。
5. artifact manifest 缺失或 checksum 不一致时，resume 视为该节点不可用，并按 checkpoint strategy 重跑或报错。

## 测试策略

### 单元测试

1. `BasicCleaner.compile()` 返回 `CleanerExecution`，不读取 dataset，不写产物。
2. `CleaningStateGraph` 根据 parameter 依赖排序，不按用户算子顺序排序。
3. `CleaningStateGraph` 对依赖环、缺少 producer、policy capability 冲突报错。
4. `NodePolicy` 合并优先级正确。
5. `PreviewPolicy` 在单算子 `preview_html()` 中作为默认值生效，显式参数能覆盖默认值。
6. `actions` 支持单值、多值和 `full`，未知 action 或 `full` 混用时报错。
7. SQLite store 能记录 run、node、stage、batch、artifact 和 event。
8. Artifact manager 能完成 tmp -> manifest -> committed -> SQLite 状态提交。

### 集成测试

1. `BasicCleaner(...).run(dataset)` 返回 `CleanerResult`，默认不在用户目录写过程产物。
2. `CleanerResult.export("clean" / "dropped" / "full")` 写出正确 Dataset。
3. `CleanerResult.export_table()`、`export_manifest()`、`export_relations()` 写出只读副本。
4. 单逻辑算子 `preview_html(operator_name=...)` 能按该算子 action/reason 和 preview policy 导出。
5. 中断后 `execution.resume(dataset=..., run_id=...)` 或 `execution.resume(dataset=..., result=...)` 跳过已完成节点并继续未完成节点。
6. batch/stage 失败触发 `RetryPolicy`，重试事件写入 SQLite。
7. evaluation-only `rerun()` 复用 parameter artifacts；parameter config 或 policy 变化时拒绝 rerun。
8. `cleanup()` 后未导出的 result 内容不可再导出。

### Notebook 验证

1. 更新清洗 v3 Notebook，使用 `result = BasicCleaner(configs).run(dataset)`。
2. 使用 `result.preview_html(..., operator_name=...)` 导出各逻辑算子预览。
3. 使用 `result.export_table()` 和 `result.export_manifest()` 显式导出调试产物，而不是读取缓存路径。

## 成功标准

1. `BasicCleaner` 成为 builder，`CleanerExecution` 执行 run/resume/rerun，`CleanerResult` 执行 state/export/preview。
2. 参数、评估和 final merge 都进入同一个阶段级 `CleaningStateGraph`。
3. SQLite 是 resume 的状态事实来源。
4. 过程产物默认隐藏在系统缓存目录，用户只能通过只读导出 API 获取副本。
5. 每个逻辑算子可以声明 `PreviewPolicy`，单算子 HTML 预览无需重复手写常用展示参数。
6. `preview()` 和 `preview_html()` 支持 `actions` 单选、多选和 `full`。
7. retry、checkpoint、resume 和 evaluation-only rerun 语义清晰且可测试。
