## Why

PR #10 的复审发现 Repo 向量归属只由应用层组合保证、跨 PostgreSQL/Iceberg 的 Schema 名称检查存在并发竞态，且外部 ModelManager 所有权与显式 Backend 初始化顺序不清晰。这些问题在正常顺序调用下不会暴露，但会削弱硬隔离、并发一致性和资源生命周期可靠性，因此必须在合并前修复。

## What Changes

- 在数据库层强制向量记录的 `repo_id` 与 `vector_field_id` 属于同一 Repo，并补充跨 Repo 负向测试。
- 为 Repo Schema 修改建立统一互斥边界：PostgreSQL 使用 Repo 级 session advisory lock，SQLite/local 使用进程内 Repo 锁。
- 普通列与 VectorField 的名称规范化统一为 `strip().casefold()`，并在锁内重新检查冲突。
- 区分 DatasetManager 内部创建与外部注入 ModelManager 的所有权，避免关闭共享资源。
- 调整显式 Backend 构造顺序，在绑定 ModelManager 前完成数据库初始化。
- 同步 VectorField、ModelManager 与 Dataset 范围 Generation 的 OpenSpec 职责描述。
- 明确本 change 不拆分管理员迁移与运行时连接；PostgreSQL 连接继续默认具备执行当前 migration 的管理员权限。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `dataset-repositories`: 将 Repo 硬隔离扩展为数据库可验证的向量字段归属约束，并明确显式 Backend 首次初始化行为。
- `repository-vectors`: 统一 VectorField 名称冲突规则，并要求跨普通列/向量字段的并发 Schema 修改保持互斥。
- `iceberg-datasets`: 普通列新增与 VectorField 新增共享 Repo Schema 锁和大小写不敏感的名称空间。
- `model-manager`: 明确 DatasetManager 对内部创建与外部注入 ModelManager 的资源所有权。
- `vector-search`: 修正 Generation 范围描述，区分 VectorField、Dataset.generate_embed 与 ModelManager 的职责。

## Impact

影响 DatasetManager control schema、初始 Alembic migration、DatasetManager 生命周期和 Schema facade 内部实现，以及相应单元/真实 PostgreSQL 并发与约束测试。公共调用签名保持不变，不新增运行时依赖，不实现最小权限 runtime 部署或独立 migration CLI。
