## ADDED Requirements

### Requirement: CleaningStateGraph 状态图编译
系统 SHALL 提供 `CleaningStateGraph`，把已配置算子列表和注册表编译为包含参数节点和评估节点的有向状态图。

#### Scenario: 编译状态图
- **WHEN** 调用 `CleaningStateGraph.compile(configured_operators, registry)`
- **THEN** 返回包含 nodes 和 plan_hash 的 CleaningStateGraph 对象

#### Scenario: 节点类型
- **WHEN** 检查编译后的 nodes
- **THEN** 包含 parameter 类型节点（参数计算）和 evaluation 类型节点（算子评估）

#### Scenario: 依赖关系
- **WHEN** 检查评估节点的 upstream_node_ids
- **THEN** 指向其依赖的参数节点

#### Scenario: 状态图序列化
- **WHEN** 调用 `to_frame()` 序列化状态图
- **THEN** 返回包含 node_id、node_type、operator_name、computer_name、required_parameters、produced_parameters 等列的 DataFrame

### Requirement: CleaningRuntime 运行时执行
系统 SHALL 提供 `CleaningRuntime`，执行状态图并生成参数表、评估表、算子输出和运行状态。

#### Scenario: 运行清洗图
- **WHEN** 调用 `CleaningRuntime(cache_root).run_graph(graph, dataset, run_options)`
- **THEN** 按 run_id 在 cache_root 下创建运行目录，执行参数计算和算子评估

#### Scenario: 运行结果状态
- **WHEN** 运行完成
- **THEN** 返回 RuntimeRunResult，包含 run_id、cache_root、status 和 attempt_count

#### Scenario: 进度回调
- **WHEN** 运行时传入 progress_callback
- **THEN** 每个节点开始和完成时通过 callback 上报 RuntimeEvent

### Requirement: 运行状态存储与恢复
系统 SHALL 提供 `JsonRunStateStore` 和 `SQLiteRunStateStore` 两种状态存储，支持断点恢复。

#### Scenario: JSON 状态保存
- **WHEN** 运行完成后
- **THEN** 在运行目录写出 state.json，包含 run_id、dataset_fingerprint、operator_states 等字段

#### Scenario: JSON 状态加载
- **WHEN** 调用 `JsonRunStateStore().load(path)` 读取有效的 state.json
- **THEN** 返回 CleanerRunState 对象

#### Scenario: 原子写入
- **WHEN** 保存状态文件
- **THEN** 先写临时文件再原子替换，避免写入中断产生损坏文件

#### Scenario: 读取运行状态
- **WHEN** 调用 `read_result_status(cache_root, run_id)`
- **THEN** 从 SQLite 数据库读取运行状态字符串

### Requirement: CleanerExecution 编译与运行入口
系统 SHALL 提供 `CleanerExecution`，作为 BasicCleaner 编译后的执行实例，封装状态图、运行时和结果。

#### Scenario: 编译计划
- **WHEN** 调用 `execution.plan()`
- **THEN** 返回编译计划 DataFrame

#### Scenario: 执行清洗
- **WHEN** 调用 `execution.run(dataset)`
- **THEN** 返回 CleanerResult 对象

#### Scenario: Dry-run 诊断
- **WHEN** 调用 `build_dry_run_result(graph, configured_operators, dataset)`
- **THEN** 返回 DryRunResult，包含 selected_operators、graph_nodes、estimated_artifacts 和 preview_policies

### Requirement: CleanerResult 运行结果
系统 SHALL 提供 `CleanerResult`，封装清洗运行的参数表、评估表、算子输出和导出能力。

#### Scenario: 获取状态摘要
- **WHEN** 调用 `CleanerResult.state()`
- **THEN** 返回各算子运行状态的 DataFrame

#### Scenario: 导出清洗产物
- **WHEN** 调用 `CleanerResult.export(kind="clean", path)`
- **THEN** 按 merge policy 生成 clean Dataset 并写出

#### Scenario: 导出调试包
- **WHEN** 调用 `CleanerResult.export_debug_bundle(path)`
- **THEN** 生成包含表、manifest、状态和 relation 副本的 zip 文件

#### Scenario: 复制 relation 表
- **WHEN** 调用 `CleanerResult.copy_relation("perceptual_duplicate", path)`
- **THEN** 复制对应 relation parquet 文件到目标路径

#### Scenario: 预览
- **WHEN** 调用 `CleanerResult.preview(limit=20)`
- **THEN** 返回 PreviewResult，包含 total_count、clean_count、dropped_count 等统计
