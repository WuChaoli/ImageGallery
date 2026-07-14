## MODIFIED Requirements

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
