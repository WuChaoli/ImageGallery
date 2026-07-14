## MODIFIED Requirements

### Requirement: before_run_check 生命周期钩子
系统 SHALL 提供 `ParameterComputer.before_run_check()` 钩子，在运行前校验依赖和资源。

#### Scenario: 默认空钩子
- **WHEN** 某个 ParameterComputer 未覆盖 before_run_check
- **THEN** 默认实现为空操作，不阻断运行

#### Scenario: 语义算子依赖检查
- **WHEN** SemanticEmbeddingComputer 的 before_run_check 检测到 ONNX 模型未安装
- **THEN** 在 compile/dry-run 阶段抛出 `SemanticDependencyError`，提示安装 `image-gallery[semantic]`

#### Scenario: 语义模型路径检查
- **WHEN** SemanticEmbeddingComputer 的 before_run_check 检测到用户显式指定的 model_path 不可访问
- **THEN** 抛出 FileNotFoundError 并提示模型下载方式

#### Scenario: run_graph 入口调用
- **WHEN** CleaningRuntime.run_graph() 开始执行参数节点前
- **THEN** SHALL 收集所有用到的 ParameterComputer 并逐个调用 before_run_check()

#### Scenario: dry-run 阶段调用
- **WHEN** build_dry_run_result() 执行诊断时
- **THEN** SHALL 对所有涉及的 ParameterComputer 调用 before_run_check()
