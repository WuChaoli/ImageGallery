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
