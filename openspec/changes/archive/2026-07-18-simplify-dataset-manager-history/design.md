## Context

`DatasetManager` 已把 durable journal 和 Repo 控制面存储拆成私有组件，但 `manager.py` 仍直接实现 Dataset 历史协议、Iceberg ref 操作、候选 Snapshot 发布和当前公开可达的未完成操作恢复，同时包含既有 pending vector 内部 helper。这些方法共享 Catalog、控制面事务和 operation journal，适合形成一个内聚的私有协作者；公开 `Dataset`、`DatasetRepo` 和 `DatasetManager` 入口必须保持不变。

## Goals / Non-Goals

**Goals:**

- 让 `DatasetManager` 只保留公开生命周期编排及对私有历史协作者的薄委托。
- 把 commit、clone、checkpoint、branch、rollback、候选发布和当前公开可达的 durable recovery 协议集中到一个可独立审查的私有模块。
- 由既有端到端特征测试和新增结构契约共同证明公开、持久化、异常、Hook 与事务语义不变。

**Non-Goals:**

- 不改变公开导出、签名、返回值或异常类型。
- 不改变数据库 Schema、operation kind/phase、intent 字段或 Iceberg ref 命名与时序。
- 不移动 Tag、VectorField、embed、DatasetView scan/read/verify 等职责。
- 不让当前 commit 路径不可达的非空 pending vector 分支成为新的公开能力、测试 fixture 或产品恢复承诺。

## Decisions

### 使用单个窄私有历史协作者

新增 `_dataset_history.py`，由 `DatasetHistory` 持有 Catalog、控制面 Engine、StorageManager、OperationJournal 和 RepositoryStore。`DatasetManager` 在初始化时创建该组件，模型层仍调用 `DatasetManager` 的原内部入口，这些入口仅转发给协作者。

选择单个组件而不是按每个操作拆多个类，因为 commit、恢复和候选发布共享同一 operation intent 与事务边界；进一步拆分会增加跨对象协议和抽象数量。

### 用私有 owner 适配层保留非历史职责边界

历史协作者持有仅供包内使用的 `DatasetManager` owner 引用，并通过 `TYPE_CHECKING` 避免运行时循环导入。clone 和 commit 只复用 owner 已有的行规范化、固定 View 扫描、按 ID 获取 Dataset 等非历史入口；这些实现不迁入协作者，模型对象也继续只保存原 `DatasetManager`，避免增加新的公开或跨层协议。

### 保留 durable protocol 的逐步骤顺序

实现按原顺序迁移 operation start、候选写入、Hook phase、intent 更新、ref 发布、存储验证和 finalize。恢复继续按持久化 kind 分派，并对当前公开 commit 可达的候选与 ref 已发布状态幂等处理；不合并事务、不重命名 phase、不更改临时 ref。既有 pending vector helper 只随代码机械迁移：当前 commit 固定产生空 pending 集合，本轮不新增内部 fixture 或公开入口来触达其非空分支。

### 以结构测试加现有行为测试验证重构

先添加导入和装配结构测试并确认其因私有组件不存在而失败，再迁移实现使其通过。既有 DatasetManager 历史、生命周期、clone、公开 API 与集成测试继续作为行为特征基线。

## Risks / Trade-offs

- [风险] 私有 owner 引用可能扩大职责边界 → 结构测试禁止协作者暴露 Tag、VectorField、embed 与 View IO 能力，代码审查限制其只调用既有窄入口。
- [风险] 迁移代码时改变 Hook 或事务时序 → 保持语句顺序机械迁移，运行当前公开可达的候选写入、ref 发布中断恢复测试和真实 Backend 验收。
- [风险] 新模块覆盖率下降 → 所有历史公开入口均通过协作者执行，并对恢复分支运行 `test-all` 与覆盖率门禁。
- [权衡] `DatasetManager` 暂时保留薄私有方法 → 这是模型对象的稳定内部适配层，可避免同时改动模型调用协议和扩大变更范围。

## Migration Plan

1. 建立结构测试并记录预期失败。
2. 新增私有历史组件并在 `DatasetManager` 初始化时装配。
3. 将历史与当前公开可达恢复方法机械迁移，保留 Manager 薄委托；既有 pending vector helper 仅随实现迁移。
4. 运行单元、完整、覆盖率和真实 Dataset Backend 验收。

无需数据迁移；回滚本次代码提交即可恢复原单文件实现。

## Open Questions

无。
