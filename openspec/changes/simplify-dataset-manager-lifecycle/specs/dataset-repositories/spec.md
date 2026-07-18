## ADDED Requirements

### Requirement: DatasetManager 生命周期语义稳定

系统 SHALL 在内部控制面职责拆分后保持 Backend、Repo、Dataset 与 Storage Prefix 的公开生命周期和资源所有权语义不变。

#### Scenario: 资源所有权保持不变

- **WHEN** DatasetManager 关闭 factory 创建的资源或调用方注入的 ModelManager
- **THEN** 只关闭自身拥有的 Engine 和 ModelManager，外部注入实例仍由调用方管理，重复关闭不会重复释放资源

#### Scenario: Repo 与 Dataset 可见性保持原子

- **WHEN** Repo namespace 或 Dataset table 已创建但控制面 finalize 尚未完成
- **THEN** 普通 list/open API 不返回半创建对象，recovery 可根据 durable intent 幂等完成

#### Scenario: 名称与 Repo 隔离保持不变

- **WHEN** 创建仅大小写或首尾空白不同的 Repo/Dataset 名称，或使用另一个 Repo 的对象
- **THEN** 继续执行相同的规范化冲突与跨 Repo 拒绝规则，并在外部副作用前失败

#### Scenario: Storage Prefix 重启恢复

- **WHEN** DatasetManager 重启并打开已有控制面
- **THEN** 已绑定 Prefix 定义重新注册到 StorageManager，授权范围和不可移除语义与重构前一致
