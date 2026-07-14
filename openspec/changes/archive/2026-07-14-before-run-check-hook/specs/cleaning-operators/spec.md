## MODIFIED Requirements

### Requirement: ParameterComputer 参数计算单元
系统 SHALL 提供 `ParameterComputer` 抽象基类，作为参数节点的计算后端，支持按 ExecutionMode 声明执行模式和运行前依赖校验。

#### Scenario: 参数计算单元注册
- **WHEN** 调用 `create_default_registry()` 创建默认注册表
- **THEN** 注册了 ImageMetadataComputer、TableDerivedComputer、ImageQualityComputer、ImageQualityDetailComputer、ImageBorderComputer、ImageHashComputer、DuplicateGroupComputer、SemanticEmbeddingComputer 等参数计算单元

#### Scenario: 语义嵌入提供者
- **WHEN** 创建注册表时传入 semantic_providers
- **THEN** SemanticEmbeddingComputer 使用指定的提供者进行语义嵌入计算

#### Scenario: before_run_check 默认空操作
- **WHEN** ParameterComputer 子类未覆盖 before_run_check 方法
- **THEN** 调用 before_run_check() SHALL 为空操作，不抛出异常

#### Scenario: before_run_check 签名
- **WHEN** 检查 ParameterComputer.before_run_check 方法签名
- **THEN** SHALL 接受可选 config 参数并返回 None，未传 config 时仍可作为默认空操作调用
