## ADDED Requirements

### Requirement: DatasetManager 尊重 ModelManager 所有权
DatasetManager SHALL 关闭由自身内部创建的 ModelManager，并 MUST NOT 关闭调用方注入的 ModelManager；外部注入实例的最终关闭责任属于调用方。

#### Scenario: 关闭内部模型管理器
- **WHEN** DatasetManager 未接收外部 ModelManager 且自身被关闭
- **THEN** 内部 ModelManager 及其已加载 provider runtime 被关闭

#### Scenario: 共享外部模型管理器
- **WHEN** 两个 DatasetManager 共享调用方注入的 ModelManager 且其中一个关闭
- **THEN** 外部 ModelManager 保持可用，另一个 DatasetManager 仍可执行模型推理

#### Scenario: 重复关闭 DatasetManager
- **WHEN** DatasetManager 被重复关闭
- **THEN** 每个由其拥有的资源最多关闭一次且不产生新异常
