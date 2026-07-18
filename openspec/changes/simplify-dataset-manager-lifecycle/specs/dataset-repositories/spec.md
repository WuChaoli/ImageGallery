## ADDED Requirements

### Requirement: DatasetManager 生命周期语义稳定

系统 SHALL 在内部控制面职责拆分后保持 Backend、Repo、Dataset 与 Storage Prefix 的公开生命周期和资源所有权语义不变。

#### Scenario: 资源所有权保持不变

- **WHEN** DatasetManager 关闭 factory 创建的资源或调用方注入的 ModelManager
- **THEN** 只关闭自身拥有的 Engine 和 ModelManager，外部注入实例仍由调用方管理，重复关闭不会重复释放资源

#### Scenario: Repo 控制面可见性保持不变

- **WHEN** Iceberg namespace 已存在但 Repo 控制面记录尚不存在
- **THEN** 普通 list/open API 继续只返回已登记的 Repo，不从 Catalog 隐式推断 Repo

#### Scenario: Dataset durable 创建保持不变

- **WHEN** Dataset table 已创建但 durable operation 尚未 finalize
- **THEN** 普通 list/open API 不返回该 Dataset，`recover_operations()` 继续根据 Dataset intent 幂等完成登记

#### Scenario: 名称与 Repo 隔离保持不变

- **WHEN** 创建仅大小写不同的 Repo/Dataset 名称，或使用另一个 Repo 的对象
- **THEN** 继续执行相同的大小写不敏感控制面冲突与跨 Repo 拒绝规则，不改变既有 Catalog 清理边界

#### Scenario: Storage Prefix 重启恢复

- **WHEN** DatasetManager 重启并打开已有控制面
- **THEN** 已绑定 Prefix 定义重新注册到 StorageManager，授权范围和不可移除语义与重构前一致
