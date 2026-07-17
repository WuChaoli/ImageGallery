## MODIFIED Requirements

### Requirement: 固定系统字段与开放物理 Schema
每张 Dataset Table SHALL 包含 required `asset_id`、`storage_prefix_id`、`relative_path`，optional `source_uri` 和 required `tag_ids: list<string>`；Dataset SHALL 通过 `dataset.schema` facade 读取列定义并新增可选业务列。普通列与所属 Repo VectorField SHALL 共享去除首尾空白且大小写不敏感的名称空间，并 SHALL 在同一 Repo Schema 锁内重新检查后新增。

#### Scenario: 通过 Schema facade 新增普通列
- **WHEN** 调用方执行 `dataset.schema.add_column(...)` 且名称和类型有效
- **THEN** 新可选业务列加入 Dataset Table 并可由 View 读取

#### Scenario: 选择普通列和向量字段
- **WHEN** DatasetView.scan 的 fields 同时指定存在的物理列和所属 Repo VectorField
- **THEN** 返回精确字段投影且不隐藏系统列或改变字段顺序

#### Scenario: 拒绝破坏性 Schema 演进
- **WHEN** 请求 drop、rename、change-type、修改系统字段或创建与 VectorField 规范名称相同的普通列
- **THEN** 操作失败且 Branch Head 不变

#### Scenario: 同 Repo Schema 修改互斥
- **WHEN** 多个调用方并发修改同一 Repo 中不同 Dataset 的普通列或 VectorField
- **THEN** 系统按 Repo 串行执行检查与修改，异常退出后锁可释放并允许后续修改

#### Scenario: 不同 Repo Schema 修改独立
- **WHEN** 两个调用方并发修改不同 Repo 的 Schema
- **THEN** 两个 Repo 使用不同锁域且不因全局互斥而相互阻塞
