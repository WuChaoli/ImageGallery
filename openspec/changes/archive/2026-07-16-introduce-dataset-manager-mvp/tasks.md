## 1. 新包边界与真实 Backend 测试设施

- [x] 1.1 先编写公共导入失败测试，冻结 `image_gallery.dataset_manager` 与 `image_gallery.storage_manager` 的独立导出，并断言新 API 不从旧 `dataset`/`storage` 继承或隐式转换。
- [x] 1.2 建立两个顶级包的最小模块结构、冻结 DTO/异常类型和 keyword-only 公共签名，DatasetManager 仅暴露 Backend/Repo 生命周期。
- [x] 1.3 增加 SQLAlchemy、psycopg、Alembic、PyIceberg、fsspec、s3fs、pgvector 与 testcontainers 依赖，保持现有默认测试不连接网络。
- [x] 1.4 建立 PostgreSQL+pgvector、PyIceberg SqlCatalog、隔离 warehouse、file 与 MinIO/S3-compatible 的集成测试 fixtures，并标记真实容器测试边界。

## 2. PostgreSQL 控制面与 Repo 隔离

- [x] 2.1 先写 migration 集成测试，冻结 repos、datasets、operations、operation_phases、repo_storage_bindings、tag_definitions、vector_fields、vector_validation_items、asset_vectors 和 pending_asset_vectors 表及唯一约束。
- [x] 2.2 实现 Alembic migrations 与职责隔离的 control、vectors、iceberg_catalog schema/role，断言业务 repository 不读写 Catalog 内部表。
- [x] 2.3 先写 DatasetManager/DatasetRepo 测试，覆盖 Repo 创建、打开、列出、大小写不敏感唯一名称、不可见中间态与同 Backend 多 Repo 隔离。
- [x] 2.4 实现 DatasetManager 连接生命周期和 Repo repository；每个 Repo 创建独立 Iceberg Namespace，所有 Repo 记录使用不可变 repo_id。
- [x] 2.5 增加跨 Repo 负面测试，拒绝 DatasetView、tag_id、vector_field_id 和 Repo 对象混用。

## 3. 独立 StorageManager

- [x] 3.1 先写 StorageManager 单元测试，覆盖 Prefix/credential DTO、file 与 S3-compatible 配置、secret reference 脱敏和独立于 DatasetManager 的 bytes IO。
- [x] 3.2 实现 CredentialProvider、Prefix registry、按 Backend 配置隔离的 fsspec client lifecycle，以及稳定 storage_prefix_id 解析。
- [x] 3.3 先写路径安全测试，覆盖绝对路径、`..`、反斜杠规范化、root escape、符号链接逃逸和保留 managed/tmp namespace。
- [x] 3.4 实现 POSIX relative_path 规范化、Prefix root containment 和稳定 Storage 错误映射。
- [x] 3.5 先写内容身份测试，覆盖规范 SHA-256、预期 hash 不匹配、managed 重复内容幂等和不同内容不可覆盖。
- [x] 3.6 实现临时对象写入、SHA-256 流式计算、确定性 managed promote、external reference 实际 bytes 验证和显式 verify。

## 4. Repo Storage 授权与 Dataset 创建

- [x] 4.1 先写 Repo-Prefix 多对多绑定测试，覆盖多 Prefix、多 Repo 复用、未授权引用拒绝，以及 MVP 不提供解绑/删除。
- [x] 4.2 实现 DatasetRepo bind/list Storage Prefix，并保证 Dataset 不保存第二层 Prefix 白名单。
- [x] 4.3 先写 Dataset create 故障测试，覆盖名称唯一、唯一 Table、默认 main、固定系统 Schema、Table 创建后 finalize 中断与幂等恢复。
- [x] 4.4 实现 Dataset registration、Table identifier、空 Iceberg Table/default Branch 创建和 finalize 前可见性门禁。
- [x] 4.5 实现 DatasetRepo.create_dataset/open_dataset/list_datasets，并确保 Branch/Checkpoint/commit 方法只存在于 Dataset handle。

## 5. Dataset Schema、内容身份与读取

- [x] 5.1 先写 Physical Schema 测试，冻结 asset_id、storage_prefix_id、relative_path、source_uri、tag_ids 类型，并覆盖仅 add optional column 和破坏性演进拒绝。
- [x] 5.2 实现系统字段保护、业务列 add-column 和 Iceberg field ID 安全演进。
- [x] 5.3 先写 DatasetView 测试，覆盖 Branch/Checkpoint 精确固定、任意列投影、scan/count/preview、按 asset_id 读取、未知列与不可变 handle。
- [x] 5.4 实现 DatasetView 查询 API，公开 API 不接受任意 snapshot_id，也不提供写入或 ref move。
- [x] 5.5 先写图片 IO 集成测试，覆盖一行一组 Prefix/path、source_uri 不参与路由、托管/外部读取、显式完整性验证和 Prefix 解析失败。
- [x] 5.6 实现 DatasetView.read_image/iter_images，对象 IO 全部委托独立 StorageManager。

## 6. Branch、Checkpoint 与乐观并发

- [x] 6.1 先写 Branch/Checkpoint 集成测试，覆盖普通 Commit 不自动建 Checkpoint、Checkpoint-only 历史、从 Checkpoint 分支和内部 Snapshot 不可公开访问。
- [x] 6.2 实现 Iceberg Branch/Tag adapter，以及 Dataset.create_branch/create_checkpoint/list/open 的领域 API。
- [x] 6.3 先写 rollback 测试，覆盖同 lineage 祖先 Checkpoint 成功、非祖先拒绝和已有 DatasetView 不漂移。
- [x] 6.4 实现同 lineage rollback，并要求非祖先状态使用从 Checkpoint 创建新 Branch。
- [x] 6.5 先写并发测试，覆盖 Commit、Tag assignment、Schema add-column、Checkpoint 和 rollback 的 stale DatasetView 基线冲突。
- [x] 6.6 实现不透明 View 基线、Branch Head CAS 和稳定 conflict error，不自动 merge、覆盖或重试。

## 7. Dataset Commit 与版本化 Tag Assignment

- [x] 7.1 先写完整行 commit 测试，覆盖 append/upsert、单 Snapshot 内 asset_id 唯一、非法 hash、重复 ID、类型错误、完整替换和 no-op。
- [x] 7.2 实现不可变 change set 与 preflight，在任何外部副作用前校验基线、Schema、Repo Prefix、row identity 和图片 SHA-256。
- [x] 7.3 先写 Repo Tag Definition 测试，覆盖 Repo 内名称唯一、跨 Repo 同名、重命名、归档和不可变 tag_id。
- [x] 7.4 实现 DatasetRepo Tag Definition API；Definition 存 PostgreSQL，Assignment 不在 PostgreSQL 建表或复制。
- [x] 7.5 先写 Tag Assignment 测试，覆盖同 asset 跨 Dataset 差异、Branch 隔离、Checkpoint 固定、去重排序、归档 Tag 不可新增和 no-op。
- [x] 7.6 实现 tag_ids 普通 Iceberg 字段写入，并与 managed/external 图片行在同一候选 Snapshot 发布。
- [x] 7.7 实现普通 Commit durable intent、Storage prepare、operation temporary ref、candidate Snapshot、official Branch CAS、finalize 和临时 ref 清理。

## 8. Repo VectorField 与组合提交

- [x] 8.1 先写 VectorField 测试，覆盖 Repo 内名称唯一、跨 Repo 隔离、空间参数与有序验证集原子创建、创建后全部参数不可修改。
- [x] 8.2 实现 DatasetRepo.create/get/list_vector_field 和冻结 VectorField handle，保存 probe bytes/hash、expected embedding 与比较契约。
- [x] 8.3 先写完整验证集门禁测试，覆盖缺项、乱序、维度、容差、NaN/Inf 和任一失败整批不写。
- [x] 8.4 实现 VectorField.write 的 source DatasetView 成员验证、单 transaction 写入和 inserted/updated/skipped 结果。
- [x] 8.5 增加默认 skip、显式 overwrite 和 Vector-only 测试，证明所有 Iceberg Branch、Snapshot 和 Checkpoint 不变。
- [x] 8.6 先写组合 Commit 故障矩阵，覆盖候选新行成员证明、多个 VectorField、验证失败、pending 写入失败、Branch CAS 冲突和 finalize 中断。
- [x] 8.7 实现 pending vectors、字段级 active-operation gate 和 Data+Vector 原子可见发布；DatasetManager 不实现 Generation 或 model API。
- [x] 8.8 增加 Repo 当前值测试，证明同 asset 跨 Dataset/Branch/Checkpoint 读取同一当前向量，Checkpoint rollback 不回滚向量。

## 9. Dataset 状态 Clone

- [x] 9.1 先写 Clone 集成测试，覆盖 Branch Head/Checkpoint View、同 Repo限制、名称冲突、固定源状态和源 Branch 后续推进不影响 Clone。
- [x] 9.2 实现 DatasetRepo.clone_dataset，创建独立 Table/main 并复制源 Physical Schema 与全部行，仅产生一次初始 Snapshot。
- [x] 9.3 增加资源复用测试，证明 Clone 不复制图片 bytes、不复制 Repo 向量、不继承任何 Branch/Checkpoint/Snapshot/operation history。
- [x] 9.4 增加 Clone 故障注入和 recovery，保证 Table/批量写入/finalize 任一点中断均不暴露半创建 Dataset。

## 10. Recovery、端到端与质量门禁

- [x] 10.1 建立 operation recovery coordinator，逐项探测 PostgreSQL、Storage、Iceberg ref 和 pgvector 实际状态并幂等 roll-forward，不物理删除对象。
- [x] 10.2 增加 create、commit、managed promote、Checkpoint、rollback、组合向量和 Clone 的关键故障点恢复测试。
- [x] 10.3 实现真实端到端：创建两个 Repo、注册并授权 file/S3 Prefix、创建 Dataset、managed/external commit、Tags、Vectors、Checkpoint、Branch、冲突和状态 Clone。
- [x] 10.4 增加 invariant audit，断言每 Dataset 一 Table、每 Repo 一 Namespace、PG 无 Tag Assignment/Branch/Checkpoint/Asset Registry 副本、向量按 Repo/Field/hash 唯一。
- [x] 10.5 运行 `uv run python -m tools.ci format-check`、`uv run python -m tools.ci lint` 和新包 scoped pytest/coverage，修复所有新增错误并保证核心新模块行覆盖率不低于 90%。
- [x] 10.6 运行现有默认测试、`openspec validate introduce-dataset-manager-mvp --strict` 与 `git diff --check`，确认旧 Dataset/Storage 行为未被新平台修改。

## 11. 明确延后范围

- [x] 11.1 在公共 docstring 与测试中明确 MVP 不提供 merge、跨 Repo clone、完整历史继承、diff、rebase、cherry-pick 或 stash。
- [x] 11.2 明确不提供 Dataset 行/Repo/Dataset/Branch/Checkpoint/Prefix/向量/托管对象删除、archive、retention、引用计数或 GC。
- [x] 11.3 明确不提供 Storage alias/解绑/在线凭证轮换、多个 locator fallback、Asset Registry 或外部引用验证缓存。
- [x] 11.4 明确不提供 Vector Generation、模型管理、历史向量、ANN、语义搜索或现有 semantic_duplicate 迁移。
