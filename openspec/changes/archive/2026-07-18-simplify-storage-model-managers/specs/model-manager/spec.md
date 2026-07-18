## ADDED Requirements

### Requirement: ModelManager 内部重构兼容性
系统 SHALL 在冻结定义、持久化注册与 provider runtime 职责拆分后保持 ModelManager 的公开导出、方法签名、数据库 schema、注册/查询、Engine 绑定、凭证隔离、runtime 缓存、输出校验与关闭生命周期语义不变。

#### Scenario: 冻结定义注册保持
- **WHEN** 调用方注册新定义、重复注册相同定义或以相同 ID 注册不同定义
- **THEN** 系统保持原有指纹、幂等结果、持久化内容与身份冲突错误

#### Scenario: Engine 绑定迁移保持
- **WHEN** ModelManager 从自有内存 Engine 绑定到 DatasetManager 控制数据库
- **THEN** 系统迁移已有冻结定义、切换为外部 Engine 所有权并只释放原自有 Engine

#### Scenario: Provider runtime 按需复用
- **WHEN** 同一模型被多次执行推理
- **THEN** 系统只在首次推理解析 credential reference 并创建 runtime，后续复用相同 runtime

#### Scenario: 非法输出整批失败
- **WHEN** provider 返回数量、维度、dtype 可转换性或有限值不满足冻结定义的输出
- **THEN** 系统返回相同 ModelRuntimeError 且不向调用方返回部分有效结果

#### Scenario: 模型资源关闭保持
- **WHEN** ModelManager 被关闭或重复关闭
- **THEN** 每个已缓存 provider runtime 至多关闭一次，后续推理被拒绝，且只有自有 Engine 被释放
