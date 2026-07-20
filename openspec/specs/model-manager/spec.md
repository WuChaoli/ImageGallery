# model-manager Specification

## Purpose

定义 DatasetManager 基础设施中的模型冻结注册、PostgreSQL 持久化恢复、凭证引用隔离、provider 运行时生命周期，以及批量图片推理的输出校验和失败边界。
## Requirements
### Requirement: ModelManager 注册冻结模型定义
ModelManager SHALL 以稳定 `model_id` 持久化注册包含 provider、artifact URI/revision/checksum、非敏感配置、credential reference、输出维度和数值类型的模型定义，并计算确定性配置指纹；相同 ID 与相同定义重复注册 SHALL 幂等成功，相同 ID 与不同定义 MUST 被拒绝。

#### Scenario: 进程重启后恢复模型
- **WHEN** DatasetManager 使用原 PostgreSQL control schema 重新启动
- **THEN** ModelManager 自动恢复相同 model_id、冻结定义和配置指纹，无需调用方重新描述模型

#### Scenario: 拒绝复用模型身份
- **WHEN** 调用方以已有 model_id 注册不同 provider、配置、维度或 dtype
- **THEN** 注册失败且原模型定义保持不变

### Requirement: ModelManager 隔离凭证和运行时资源
ModelManager SHALL 只在 provider 边界解析凭证引用，MUST NOT 在模型定义、配置指纹、公开 DTO 或日志中保存明文凭证，并 SHALL 管理缓存运行时的关闭生命周期。

#### Scenario: 关闭模型资源
- **WHEN** ModelManager 被关闭
- **THEN** 全部已加载 provider runtime 被关闭且后续推理被拒绝

#### Scenario: 模型 artifact 不可达
- **WHEN** 已恢复模型定义指向的 artifact 在离线环境中不可访问或 checksum 不匹配
- **THEN** 模型定义保持不变且推理返回明确资源错误，不得改绑其他 artifact

### Requirement: 模型推理输出具有基础契约
ModelManager SHALL 按注册定义对一批已验证图片 bytes 执行推理，并在返回前校验输出数量、维度、dtype 可转换性和所有数值有限。

#### Scenario: 模型返回非法向量
- **WHEN** provider 返回数量错误、维度错误、不可转换类型、NaN 或 Inf
- **THEN** 本批推理失败且不向调用方返回部分有效结果

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
