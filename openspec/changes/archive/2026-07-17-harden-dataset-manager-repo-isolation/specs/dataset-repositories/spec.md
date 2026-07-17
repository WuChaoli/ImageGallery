## MODIFIED Requirements

### Requirement: Repo 是硬隔离边界
系统 SHALL 以不可变 `repo_id` 隔离 Dataset、Tag Definition、VectorField 和向量，并禁止跨 Repo 引用这些对象；持久层 MUST 约束向量记录的 `repo_id` 与 `vector_field_id` 属于同一 Repo，不得只依赖应用层组合。

#### Scenario: 相同名称跨 Repo 使用
- **WHEN** 两个 Repo 分别创建同名 Dataset、Tag 或 VectorField
- **THEN** 系统允许创建且两组对象互不影响

#### Scenario: 拒绝跨 Repo 引用
- **WHEN** Dataset 写入另一个 Repo 的 tag_id、vector_field_id 或 DatasetView
- **THEN** 整个操作在产生外部副作用前被拒绝

#### Scenario: 数据库拒绝跨 Repo 向量组合
- **WHEN** 写入向量或 pending 向量时将一个 Repo ID 与另一个 Repo 所属 VectorField ID 组合
- **THEN** PostgreSQL 复合引用约束拒绝整行，即使两个 ID 各自都存在

## ADDED Requirements

### Requirement: 显式 Backend 组合先完成控制面初始化
DatasetManager SHALL 在绑定依赖 control schema 的 ModelManager 前完成 PostgreSQL migration 或本地 metadata 初始化；当前 PostgreSQL Backend MAY 假定连接具备执行 migration 的管理员权限。

#### Scenario: 全新 PostgreSQL 显式构造
- **WHEN** 调用方使用全新 PostgreSQL Engine、Catalog、StorageManager 和 ModelManager 显式构造 DatasetManager
- **THEN** control schema 与模型表先完成初始化，随后 ModelManager 成功绑定且 Repo 可创建
