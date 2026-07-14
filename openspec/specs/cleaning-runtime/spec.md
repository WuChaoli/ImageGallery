# cleaning-runtime Specification

## Purpose
TBD - created by archiving change init-specs-from-codebase. Update Purpose after archive.
## Requirements
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

### Requirement: 非阻塞运行模型（PLANNED）
系统 SHALL 将 `run()` 改为非阻塞方法返回 `CleanerRun`，新增 `run_sync()` 作为阻塞等价物。

#### Scenario: run 返回 CleanerRun
- **WHEN** 调用 `cleaner.run(dataset)`
- **THEN** 立即返回 CleanerRun 对象，清洗在后台线程执行

#### Scenario: CleanerRun.wait 阻塞等待
- **WHEN** 调用 `cleaner_run.wait()`
- **THEN** 阻塞直到清洗完成，返回 CleanerResult

#### Scenario: run_sync 等价于 run+wait
- **WHEN** 调用 `cleaner.run_sync(dataset)`
- **THEN** 阻塞执行，返回 CleanerResult（等价于 `cleaner.run(dataset).wait()`）

#### Scenario: resume 也支持非阻塞
- **WHEN** 调用 `execution.resume()`
- **THEN** 返回 CleanerRun（非阻塞）

#### Scenario: resume_sync 阻塞恢复
- **WHEN** 调用 `execution.resume_sync()`
- **THEN** 阻塞恢复，返回 CleanerResult

### Requirement: CleanerRun 协作式停止（PLANNED）
系统 SHALL 提供 CleanerRun.stop() 方法，支持协作式停止正在运行的清洗任务。

#### Scenario: 请求停止
- **WHEN** 调用 `cleaner_run.stop()`
- **THEN** 发送停止请求，运行状态从 running 变为 stopping

#### Scenario: 停止完成
- **WHEN** 后台线程检测到停止请求并完成当前批次后退出
- **THEN** 运行状态变为 stopped

#### Scenario: 停止后不可恢复
- **WHEN** 清洗已 stopped 后调用 resume
- **THEN** 抛出 CleanerRunFailedError

### Requirement: RunProgress 进度查询（PLANNED）
系统 SHALL 提供 CleanerRun.progress 属性，实时查询清洗进度。

#### Scenario: 进度结构
- **WHEN** 访问 `cleaner_run.progress`
- **THEN** 返回 RunProgress，包含 total_images、processed_images、current_node、elapsed_seconds

#### Scenario: 未完成时 result 报错
- **WHEN** 清洗尚未完成时访问 `cleaner_run.result`
- **THEN** 抛出 CleanerRunNotReadyError

### Requirement: RunStore 存储模式（PLANNED）
系统 SHALL 提供 RunStore 抽象，支持 memory、temporary、disk 三种运行存储模式。

#### Scenario: memory 模式
- **WHEN** storage="memory"
- **THEN** 表和 JSON 数据保存在进程内存中，无文件系统持久化

#### Scenario: temporary 模式（默认）
- **WHEN** storage="temporary" 或未指定
- **THEN** 使用临时目录，cleanup() 时删除

#### Scenario: disk 模式
- **WHEN** storage="disk"
- **THEN** 使用 `cache_root / run_id` 路径，支持长期保存和 resume

#### Scenario: memory 模式下语义算子报错
- **WHEN** storage="memory" 且配置了 semantic_duplicate 算子
- **THEN** before_run_check 阶段报错，提示使用 temporary 或 disk 模式

#### Scenario: RunStore 协议
- **WHEN** 检查 RunStore 接口
- **THEN** 包含 write_table、read_table、write_json、read_json、materialize_dataset、cleanup 方法

### Requirement: before_run_check 生命周期钩子（PLANNED）
系统 SHALL 提供 ParameterComputer.before_run_check() 钩子，在运行前校验依赖和资源。

#### Scenario: 默认空钩子
- **WHEN** 某个 ParameterComputer 未覆盖 before_run_check
- **THEN** 默认实现为空操作，不阻断运行

#### Scenario: 语义算子依赖检查
- **WHEN** SemanticEmbeddingComputer 的 before_run_check 检测到 ONNX 模型未安装
- **THEN** 在 compile/dry-run 阶段抛出明确依赖缺失错误

#### Scenario: 语义模型路径检查
- **WHEN** SemanticEmbeddingComputer 的 before_run_check 检测到模型路径不可访问
- **THEN** 抛出 FileNotFoundError 并提示模型下载方式

### Requirement: 核心不变量
系统 SHALL 在所有清洗运行时流程中维护以下核心不变量。

#### Scenario: image_uri 唯一引用
- **WHEN** 图片被导入到平台后
- **THEN** image_uri 是该图片在系统中的唯一主引用地址，所有后续操作（清洗、可视化、导出）均通过 image_uri 访问图片

#### Scenario: source_uri 仅用于追溯
- **WHEN** 导出 clean/dropped/full 数据集供外部消费
- **THEN** source_uri 默认不包含在导出数据集中，仅在审计和追溯场景中可用

#### Scenario: raw Dataset 不可变
- **WHEN** 清洗运行时执行算子评估和归并
- **THEN** 原始 raw Dataset 文件不被修改，clean/dropped/full 是独立的导出视图

#### Scenario: clean + dropped = full
- **WHEN** 清洗归并完成
- **THEN** clean 数据集与 dropped 数据集的并集等于 full 数据集（按 image_id 集合验证）

#### Scenario: 归并只能由 MergePolicy 生成
- **WHEN** 生成 clean、dropped、full 数据集
- **THEN** 必须通过 MergePolicy 基于逻辑算子的评估结果生成，不能由物理执行直接产出

#### Scenario: 算子按能力命名
- **WHEN** 面向用户展示或配置逻辑算子
- **THEN** 使用能力优先命名（如 blur、dimension、exact_duplicate），不暴露底层工具名称（OpenCV、fastdup、DINOv2）

#### Scenario: 单张图片失败不中断批次
- **WHEN** 某张图片在导入或清洗过程中失败
- **THEN** 该图片记录在 failure_manifest 中，其余图片继续处理

