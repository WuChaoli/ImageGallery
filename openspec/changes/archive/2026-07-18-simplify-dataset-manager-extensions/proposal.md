## Why

`DatasetManager` 已拆出生命周期和历史协议，但 Tag、VectorField、Repo Schema 锁、DatasetView IO 与向量生成仍集中在 `manager.py`，使各自的事务、并发和 Snapshot 语义难以独立审查。需要在不改变公开接口或持久化行为的前提下，把这些扩展职责收敛到窄私有协作者。

## What Changes

- 用字符化测试固定 Tag、VectorField、Repo Schema 锁、DatasetView IO 与向量生成的现有边界语义。
- 将 Tag Definition SQL、VectorField 定义和当前值存取、Repo Schema 锁生命周期、View 物理读取及当前向量合并、Dataset 范围向量生成拆入各自私有模块。
- 保留 `DatasetManager` 对跨 Catalog、Model、Storage 和锁的领域编排，以及公开 handle 构造与 manager identity。
- 保持公开导出、类、签名、异常文本、对象回引用、事务、并发、Snapshot 与当前向量语义不变。
- 不修改数据库 migration/control schema，不增加搜索、缓存、GC、DAO、Unit of Work 或依赖注入框架。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `repository-tags`: 增加内部职责拆分后必须保持 Tag 定义的 Repo 隔离、名称和事务语义不变的约束。
- `repository-vectors`: 增加内部职责拆分后必须保持 VectorField、当前向量、Schema 锁、View 合并和向量生成语义不变的约束。

## Impact

- 影响 `src/image_gallery/dataset_manager/manager.py`，并新增五个 DatasetManager 私有扩展协作模块。
- 增加职责边界及高风险行为字符化测试，更新模块 `AGENTS.md` 导航。
- 不增加依赖，不改变公开 API、数据库 Schema、migration 或产品能力。
