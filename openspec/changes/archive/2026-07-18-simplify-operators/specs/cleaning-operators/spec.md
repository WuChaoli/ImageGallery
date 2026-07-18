## ADDED Requirements

### Requirement: 默认算子工厂重构兼容性
系统 SHALL 在内部目录实现重构后保持 `create_default_registry()` 与 `create_default_metric_specs()` 的公开签名、返回类型和完整规格语义不变。每次调用 SHALL 返回可独立使用的规格与可变配置对象，不得因共享内部目录对象而产生跨注册表状态污染。

#### Scenario: 默认注册表语义保持
- **WHEN** 调用 `create_default_registry()`
- **THEN** 返回的 OperatorRegistry 包含与重构前相同顺序和字段的 17 个 OperatorSpec、相同顺序与契约的 ParameterComputer，并保持 evaluator 与 PreviewPolicy 绑定不变

#### Scenario: 默认指标语义保持
- **WHEN** 调用 `create_default_metric_specs()`
- **THEN** 返回与重构前相同键、字段和值的 17 个 MetricSpec

#### Scenario: 默认工厂对象相互独立
- **WHEN** 分别两次调用默认注册表或指标工厂
- **THEN** 一次调用所得可变配置或策略对象的修改不会影响另一次调用结果

#### Scenario: 语义提供者注入保持
- **WHEN** 使用 `semantic_providers` 调用 `create_default_registry()`
- **THEN** 注册的 SemanticEmbeddingComputer 继续使用该提供者映射
