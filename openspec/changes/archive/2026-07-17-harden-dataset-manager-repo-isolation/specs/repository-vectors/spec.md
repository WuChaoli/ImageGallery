## MODIFIED Requirements

### Requirement: VectorField 属于 DatasetRepo
DatasetRepo SHALL 通过 `repo.schema` facade 管理 Repo 内命名唯一的 VectorField；每个字段 SHALL 锁定已注册 `model_id`、模型配置指纹、维度、数值类型和距离度量。VectorField 与 Repo 内任一 Dataset 普通列 SHALL 共享去除首尾空白且大小写不敏感的名称空间，并 SHALL 在 Repo 级 Schema 锁内重新检查后创建。

#### Scenario: 创建模型绑定字段
- **WHEN** 调用方执行 `repo.schema.add_vector(name, model_id, distance)` 且模型已注册
- **THEN** 字段定义和冻结模型信息在一个 PostgreSQL transaction 中可见或均不可见

#### Scenario: 拒绝未知模型
- **WHEN** 创建 VectorField 时 model_id 未在 DatasetManager 的 ModelManager 注册
- **THEN** 创建失败且不产生部分字段元数据

#### Scenario: 拒绝大小写不同的普通列冲突
- **WHEN** Repo 任一 Dataset 已有普通列 `Embedding` 且调用方创建名为 ` embedding ` 的 VectorField
- **THEN** 创建失败且不产生 VectorField

#### Scenario: 并发创建同名普通列和 VectorField
- **WHEN** 同 Repo 的普通列新增与 VectorField 新增以相同规范名称并发执行
- **THEN** 两个操作串行重新检查，最多一个成功且最终 Schema 不存在歧义字段
