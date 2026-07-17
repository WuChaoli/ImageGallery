## Context

现有 `image_gallery.dataset` 以 Parquet/CSV/JSONL 文件为身份，`image_gallery.storage` 直接暴露文件系统与 MinIO 实例。新平台是全新设计，不迁移旧调用方，也不以旧公开 API、`image_uri` 契约或内部架构作为兼容边界。

平台需要同时解决四个不同层次的问题：通用图片 bytes 存储、多个 Dataset 的注册与隔离、单 Dataset 的 Iceberg 历史，以及跨 Dataset 共享的 Tag Definition 与当前向量。把这些方法全部集中到 Manager 或 Dataset 都会形成过重聚合根，因此本设计拆分 `storage_manager` 与 `dataset_manager` 两个顶级包，并在 Dataset 上增加 DatasetRepo。

## Goals / Non-Goals

**Goals:**

- 交付 `DatasetManager → DatasetRepo → Dataset → DatasetView` 的真实 Backend MVP。
- 每个 Dataset 使用一张 Iceberg Table，以 Branch 表达工作线、以 Checkpoint 表达唯一公开历史。
- 使用 SHA-256 内容身份跨 Dataset 复用图片身份和 Repo 当前向量，不建立 Asset Registry。
- 让 Dataset 提供语义 IO，同时复用独立 StorageManager 的物理 IO。
- 支持版本化 Tag Assignment、Repo 级 VectorField、组合提交和同 Repo 状态 Clone。
- 对 PostgreSQL、Iceberg、Storage 和 pgvector 的部分失败提供不可见门禁与可恢复操作。

**Non-Goals:**

- 不兼容、替换或迁移旧 `image_gallery.dataset`、`image_gallery.storage` 及其调用方。
- 不实现 Dataset merge、跨 Repo clone、完整历史继承、diff、rebase 或 cherry-pick。
- 不实现 Stash、删除、archive、retention、引用计数、对象/向量 GC 或历史向量。
- 不实现向量 Generation、模型管理、ANN、语义搜索或相似度产品 API。
- 不实现逻辑 Schema、隐藏列、Field Registry、drop/rename/change-type。
- 不实现 Storage Prefix 删除、解绑、alias、在线凭证轮换或通用对象管理器。

## Decisions

### 1. 两个独立顶级包，不继承旧 API

新增 `image_gallery.dataset_manager` 和 `image_gallery.storage_manager`。旧包可以继续存在，但新平台不复用其公共对象，也不提供兼容适配层。两个独立顶级包让 StorageManager 能被 Import、Cleaning 等未来功能复用；相比改造旧包，这也避免尚未稳定的新架构被历史签名限制。

`DatasetManager` 只持有 Backend 配置、连接生命周期以及 Repo 创建/打开/列出方法。它不是单 Dataset 操作入口。

### 2. DatasetRepo 是硬隔离和共享定义边界

一套 DatasetManager Backend 连接一个 PostgreSQL 实例、一个 Iceberg Catalog 和一个 Warehouse，并承载多个 DatasetRepo。每个 Repo 对应一个 Iceberg Namespace；所有 PostgreSQL 记录使用不可变 `repo_id` 隔离。Dataset 名、Tag Definition 名和 VectorField 名只在 Repo 内唯一，不允许跨 Repo 引用或查询。

DatasetRepo 负责 Dataset 注册、Tag Definition、VectorField、当前向量以及 Storage Prefix 授权。相同图片 SHA-256 可以分别出现在多个 Repo，但其 Tag 和 Vector 互不共享。

### 3. StorageManager 只执行物理对象 IO

StorageManager 负责 Credential Binding、Storage Prefix、file/S3-compatible client、规范相对路径、bytes IO、SHA-256 和托管内容寻址对象。它不依赖 DatasetManager，也不理解 Repo、Dataset、Branch、Checkpoint、Tag 或 Vector。

Prefix 在 StorageManager 全局注册，在 DatasetRepo 层形成多对多授权；Dataset 不维护第二层白名单。已经被数据引用的 Prefix 和授权在 MVP 中不可删除或解除。

Dataset/DatasetView 提供图片领域入口：它从 Iceberg 行取得 `storage_prefix_id + relative_path`，再委托 StorageManager。这样调用方无需手工拼接存储路径，但 StorageManager 仍可被其他包独立使用。

### 4. 内容哈希直接作为资产身份

公开字段名保留 `asset_id`，其规范值固定为 `sha256:<64 lowercase hex>`。托管图片由 StorageManager 对实际 bytes 计算身份；外部引用首次进入任何 Dataset 时也必须实际读取并验证。调用方提供的预期 hash 不一致时整批失败。

不建立 Repo 级 Asset Registry。每个 Dataset Snapshot 内 `asset_id` 唯一，一行只保存一组 `storage_prefix_id + relative_path`；不同 Dataset 可以为同一内容保存不同位置、业务字段和 Tag。普通读取不重复计算 hash，显式完整性验证才重新读取。

### 5. Dataset 拥有一张 Iceberg Table 和版本化行状态

Dataset 创建时同时创建空 Table 和默认 `main` Branch。固定系统字段为：required `asset_id`、`storage_prefix_id`、`relative_path`，optional `source_uri`，以及规范化为非空容器的 `tag_ids: list<string>`。用户可以读取全部系统列并增加可选业务列；MVP 只允许 add-column。

Commit 使用完整 row append/upsert，以 `asset_id` 为键；同一 change set 重复 ID、非法 hash、未授权 Prefix、Schema/Tag 错误或图片校验失败时整批拒绝。规范化后无 Iceberg 数据变化时不产生 Snapshot。

### 6. DatasetView 是精确读基线和并发令牌

打开 Branch Head 或 Checkpoint 都返回固定 Snapshot 的只读 DatasetView。View 提供 scan、count、preview、行读取和图片 bytes 读取，不提供 ref move 或写入。

所有推进 Branch 的操作必须携带目标 Branch 的精确基线 View；若 Head 已改变，操作返回稳定冲突，不自动覆盖、merge 或重试。公开 API 不接受任意内部 `snapshot_id`。

### 7. Branch 与 Checkpoint 最大化复用 Iceberg

Branch 是 Iceberg mutable ref；Checkpoint 是无限期保留的 immutable Iceberg Tag。普通 Commit 不自动创建 Checkpoint，普通历史列表只返回 Checkpoint。未被 Checkpoint 引用的 Snapshot 是内部实现事实，可按后续保留策略过期。

从历史创建 Branch 只接受 Checkpoint。Rollback 只接受当前 lineage 的祖先 Checkpoint；非祖先状态通过创建新 Branch 表达。MVP 不删除 Branch 或 Checkpoint。

### 8. Tag Definition 在 Repo，Assignment 在 Dataset

DatasetRepo 在 PostgreSQL 保存不可变 `tag_id` 及名称、颜色、描述、lifecycle。Tag 名在 Repo 内大小写不敏感唯一；Definition 可重命名或归档。

Assignment 只保存在 Iceberg `tag_ids` 字段中。写入前验证 Repo Tag ID、去重并规范排序。归档 Tag 不可新增，但历史值可读。Tag Assignment 修改是普通 Dataset commit，随 Branch 隔离并由 Checkpoint 固定。

### 9. Repo 当前向量与 Dataset 历史正交

VectorField 在 Repo 内命名唯一，并锁定维度、数值类型、距离度量、比较容差和一套有序不可变验证集。创建后所有空间与验证参数不可修改。DatasetManager 不保存模型或 Generation 身份。

向量以 `(repo_id, vector_field_id, asset_id)` 存入 pgvector。独立写入必须传精确 DatasetView，全部 ID 必须是该 View 成员；组合 commit 可用本次候选行证明成员关系。默认跳过已有值，显式 overwrite 才覆盖。Vector-only 写入不推进 Iceberg；Checkpoint 和 rollback 始终读取 Repo 当前向量。

### 10. Clone 复制状态而不继承历史

`DatasetRepo.clone_dataset(source: DatasetView, name=...)` 仅支持同 Repo。它创建新 Dataset/Table，复制源 View 的 Physical Schema 和全部行，并产生新 Dataset 的一次初始 Snapshot。新表只有自己的 `main`，不复制源 Branch、Checkpoint、Snapshot 或 operation history。

Clone 不复制图片 bytes，行继续引用相同 Prefix/path；不复制向量，因为相同 asset_id 自动读取 Repo 当前值。公开语义不承诺 Iceberg 元数据级 shallow clone，MVP 可以批量读写实现，避免未来跨表 data-file GC 风险。

### 11. 跨后端操作使用可恢复原子可见性

Dataset create、clone、managed object promote、Dataset commit、Checkpoint/ref move 和组合向量写入都先保存 durable intent。候选 Iceberg Snapshot 使用 operation 临时 ref；向量先写入 pending 区；正式 Branch CAS 与 PostgreSQL finalize 之间存在未完成操作时，该 Dataset/Branch 对普通 API 显示为 reconciling 并拒绝读写。

Recovery 必须探测 PostgreSQL、Iceberg、Storage 和 pgvector 的实际状态并幂等 roll-forward，不根据单一 phase 猜测回滚，也不物理删除可能已被引用的对象。组合提交只有在数据和向量都可发布时才对普通 API 同时可见。

### 12. MVP 名称与生命周期保持最小

Repo、Dataset、Tag、VectorField、Prefix 使用不可变内部 ID；名称按各自作用域大小写不敏感唯一。Repo、Dataset、VectorField 和 Prefix 不可重命名；Tag Definition 可重命名，因为 Assignment 引用 tag_id。MVP 不提供 Dataset 行、Repo、Dataset、Branch、Checkpoint、向量或托管对象删除。

## Risks / Trade-offs

- [外部对象可在导入后被修改] → 导入时强制按真实 bytes 校验，普通读取报告存储错误，显式 verify 重新计算；MVP 不承诺弱引用长期可用。
- [无 Asset Registry 导致相同外部引用重复校验] → 接受 MVP 读取成本，避免建立新的全局数据面；后续以实测需求决定缓存。
- [每行只有一个位置，无法自动故障转移] → MVP 保持确定读取；多副本和 locator fallback 单独设计。
- [Repo 当前向量不随 Checkpoint 回退] → API 和返回类型明确 current 语义，不把向量伪装成 Snapshot 字段。
- [Storage/Iceberg/PostgreSQL 无分布式事务] → durable intent、pending vectors、临时 ref、CAS、可见性门禁和实际状态恢复。
- [Clone 批量重写可能较慢] → 先保证独立历史与正确性；不提前承诺危险的跨表文件共享优化。
- [MVP 无删除与 GC，存储只增不减] → 生产清理前必须另立 change 设计历史引用、保留和审计。
- [新旧同名领域对象可能混淆] → 通过独立顶级包和文档明确新 API 不兼容；本 change 不提供隐式转换。

## Migration Plan

1. 新增独立包、Backend 配置、PostgreSQL migrations 和真实测试容器，不修改旧包。
2. 实现 StorageManager 与 Prefix 注册，再实现 DatasetManager/DatasetRepo 和 Repo Namespace。
3. 实现单表 Dataset、View、Branch、Checkpoint、Schema、内容身份和图片 IO。
4. 实现 Repo Tag/Vector、组合提交、Clone 和 recovery。
5. 通过独立 Notebook/API 试用新平台；旧 Import/Cleaning 迁移由后续 change 决定。

回滚时停用新包入口并回退专用 migrations；旧文件型 Dataset/Storage 不受影响。MVP 不提供生产数据物理清理。

## Open Questions

无阻塞问题。删除/GC、跨 Repo 数据移动、搜索和旧调用方迁移均已明确延后。
