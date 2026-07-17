## Context

DatasetManager 同时跨 PostgreSQL control/vector schema、PyIceberg Catalog 和 StorageManager 工作。当前顺序路径已由单元及真实 Backend E2E 验证，但复审发现三个跨边界缺口：数据库无法证明向量字段归属与 Repo 一致，普通列与 VectorField 的互斥检查无法抵御并发，资源所有权和首次初始化顺序在显式组合路径中不稳定。本 change 在 PR #10 合并前修正这些基础约束。

## Goals / Non-Goals

**Goals:**

- 让 PostgreSQL 自身拒绝跨 Repo 的向量字段组合。
- 保证同 Repo 普通列和 VectorField 的名称空间在并发下仍唯一，且大小写规则一致。
- 让 DatasetManager 只关闭自己创建的 ModelManager。
- 让显式 Backend 构造可在全新 PostgreSQL 上按正确顺序初始化。
- 消除 VectorField、ModelManager 和 Dataset Generation 之间的规范冲突。

**Non-Goals:**

- 不拆分管理员 migration 与 runtime 连接；当前 PostgreSQL URL 默认具有管理员权限。
- 不提供 migration CLI、`auto_migrate` 参数、runtime role 或现有数据库升级兼容。
- 不增加字段 rename/drop、跨 Repo clone、搜索或 ANN API。
- 不建立跨 PostgreSQL 与 Iceberg 的通用分布式事务框架。

## Decisions

### 1. 使用复合外键固化 Repo 归属

`vector_fields` 增加 `(repo_id, vector_field_id)` 唯一约束；`asset_vectors` 与 `pending_asset_vectors` 使用同一对列的复合外键。保留现有三元主键，兼顾按 Repo/Field/Asset 查询。因为初始 migration 尚未进入 master，直接更新 `0001_dataset_manager_mvp` 和 SQLAlchemy metadata，不新增兼容 migration。

备选方案是从向量表移除 `repo_id` 并通过 VectorField join 推导；它可消除冗余，但会改变热点查询和主键，因此本轮不采用。

### 2. Schema 修改使用 Repo 级跨 facade 锁

PostgreSQL 使用 session advisory lock，而不是 transaction advisory lock：锁必须覆盖 PostgreSQL 检查、Iceberg Schema commit 和 PostgreSQL VectorField insert，且不应为了外部 Iceberg IO 长时间保持数据库事务。锁 key 由固定 namespace 常量与 `repo_id` 的稳定哈希生成，获取锁的专用 connection 在上下文退出时于 `finally` 显式解锁并关闭。

SQLite/local 使用 DatasetManager 实例内的 `repo_id -> threading.RLock`。锁映射只作为进程内测试 Backend 协调器，不承诺跨进程 SQLite 互斥。两个 facade 都通过同一内部 context manager，并在获得锁后重新读取物理列和 VectorField。

同 Repo Schema 变更串行，不同 Repo 使用不同 key 并可并行；scan、commit、generate_embed 不获取该锁。

### 3. 名称使用统一规范键

普通列和 VectorField 的冲突键统一为 `name.strip().casefold()`，展示/存储名称保留 trim 后原始大小写。VectorField 本身继续由数据库 `name_key` 唯一约束保护；普通列与 VectorField 的跨存储冲突由锁内双向检查保护。

### 4. 显式记录 ModelManager 所有权

构造时仅在 `model_manager is None` 时设置 `_owns_model_manager=True`。`close()` 只关闭内部创建实例；外部注入实例由调用方关闭。Engine/Catalog 的现有所有权规则保持不变。

### 5. 先初始化数据库再绑定 ModelManager

构造顺序调整为保存依赖、执行 PostgreSQL migration 或 SQLite metadata 初始化、创建/绑定 ModelManager、恢复 Prefix。`.postgres()` 当前的提前 migration 可保留幂等执行，也可在实现时去重，但不得让 Catalog 在基础 schema 之前初始化。

### 6. Generation 规范按职责而非是否存在划分

VectorField 只描述冻结向量空间，不直接执行 Generation；ModelManager 管理模型定义与推理运行时；`Dataset.generate_embed()` 固定 Dataset/View 成员并发布 Repo 当前值。vector-search 仍不包含 ANN 或搜索 API。

## Risks / Trade-offs

- [持有 advisory lock 时 Iceberg 操作较慢] → 锁仅限同 Repo Schema 变更，不阻塞数据读写，并用真实并发测试验证不同 Repo 不互相阻塞。
- [异常导致 session lock 泄漏] → 使用专用 connection 和 `try/finally` 解锁；测试注入失败后再次获取同 Repo 锁。
- [SQLite 跨进程仍可能竞态] → local 是测试 Backend，本轮只承诺单进程互斥；真实跨进程保证由 PostgreSQL 测试覆盖。
- [直接修改初始 migration 不支持已部署数据库] → PR 尚未合并且仓库允许快速转向；若 master 后已有部署，需另行创建升级 migration。
- [外部 ModelManager 调用方忘记关闭] → 所有权规则写入 docstring/AGENTS，并通过上下文测试明确责任。

## Migration Plan

1. 更新 SQLAlchemy metadata 和初始 Alembic migration。
2. 在隔离 PostgreSQL 中重新建库并验证复合外键。
3. 以失败测试驱动所有权、初始化顺序、名称规则和并发锁实现。
4. 同步主 specs、README/AGENTS 后归档 change。
5. 重新执行完整 PR 门禁与独立代码审查；无阻断问题后合并 PR #10。

回滚通过撤销本 change 提交实现；由于 change 在首次合并前完成，不提供线上 schema downgrade 数据迁移。

## Open Questions

无。管理员权限 migration 是已确认的当前部署前提，最小权限运行时能力留待后续独立 change。
