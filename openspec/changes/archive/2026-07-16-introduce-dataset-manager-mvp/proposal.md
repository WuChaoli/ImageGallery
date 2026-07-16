## Why

当前文件型 Dataset 无法统一表达可分支的 Iceberg 数据、跨 Dataset 共享的内容身份与向量，以及可复用的图片存储。此前规划把 Dataset 自身作为所有能力的聚合根，导致 Tag、Vector、Storage 和单 Dataset 生命周期耦合；新平台需要以 DatasetRepo 管理多个 Dataset，并重新设计不受旧 API 约束的边界。

## What Changes

- 新增独立 `image_gallery.dataset_manager` 包；其 API 和架构不受现有 `image_gallery.dataset` 兼容性限制，`DatasetManager` 只负责 Backend 生命周期和 DatasetRepo 创建/打开。
- 新增 DatasetRepo 聚合根：一套 Backend 承载多个 Repo，每个 Repo 对应一个 Iceberg Namespace，并隔离 Dataset、Tag Definition、VectorField 和向量。
- 每个 Dataset 只维护一张 Iceberg Table；Branch 使用 Iceberg Branch，Checkpoint 使用不可变 Iceberg Tag，普通历史只通过 Checkpoint 暴露。
- Dataset、DatasetView 承担单 Dataset 的 Schema、Branch、Checkpoint、commit、scan 和图片语义 IO；Manager 不承载 Dataset 局部方法。
- 固定 `asset_id = SHA-256(image bytes)`；不建立 Repo 级 Asset Registry，同一 Dataset Snapshot 内每个 `asset_id` 最多一行。
- Dataset 行固定保存 `asset_id`、`storage_prefix_id`、`relative_path`、可选 `source_uri` 和版本化 `tag_ids`，并允许新增用户业务列。
- Tag Definition 提升到 DatasetRepo；Tag Assignment 留在 Dataset Iceberg 行中，因此同一内容在不同 Dataset、Branch 和 Checkpoint 中可以拥有不同 Tag。
- VectorField、不可变验证集和 pgvector 当前向量提升到 DatasetRepo；向量按 `(vector_field_id, asset_id)` 跨 Dataset 复用，不随 Dataset Checkpoint 回退。
- 新增独立 `image_gallery.storage_manager` 包，供 DatasetManager 和其他功能复用；StorageManager 负责 Prefix、凭证、路径安全、bytes IO、内容哈希和托管对象，不理解 Dataset 领域。
- Storage Prefix 在 StorageManager 中注册、在 DatasetRepo 层授权；一个 Repo 可使用多个 Prefix，一个 Prefix 可供多个 Repo 使用。
- 新增从精确 DatasetView 克隆 Dataset 当前状态的能力；Clone 创建新 Iceberg Table，但不继承 Branch、Checkpoint 或 Snapshot 历史，也不复制图片 bytes 和 Repo 级向量。
- 所有 Branch 推进使用显式 DatasetView 基线和乐观并发控制；Data + Vector 组合提交保持跨 Iceberg、Storage 和 pgvector 的原子可见性。
- MVP 不实现 merge、跨 Repo clone、stash、删除、GC、历史向量、向量生成、ANN 或语义搜索。

## Capabilities

### New Capabilities

- `dataset-repositories`: DatasetManager Backend、DatasetRepo 注册/隔离、命名空间、共享定义和 Repo 级 Storage Prefix 授权。
- `iceberg-datasets`: 单表 Dataset、系统字段、Physical Schema、DatasetView、commit、Branch、Checkpoint、图片 IO 和状态 Clone。
- `storage-manager`: 独立 StorageManager、Prefix/凭证注册、file 与 S3-compatible IO、内容哈希、托管对象和外部引用验证。
- `repository-tags`: DatasetRepo 级 Tag Definition，以及 Dataset Iceberg 行中随历史版本化的 Tag Assignment。
- `repository-vectors`: DatasetRepo 级锁定 VectorField、不可变验证集、pgvector 当前值、来源 View 成员门禁和组合提交。

### Modified Capabilities

- `dataset-versioning`: 将未来的抽象 Version/merge/diff 占位改为单 Dataset Iceberg Branch、Checkpoint-only 历史、乐观并发和状态 Clone。
- `vector-search`: 将未来向量归属从 Dataset 扩展列改为 DatasetRepo 级 VectorField/pgvector 当前值；搜索、索引和 Generation 仍不在 MVP。

## Impact

- 新增 `src/image_gallery/dataset_manager/` 与 `src/image_gallery/storage_manager/`，不复用或兼容旧文件型 Dataset/Storage API。
- 新增 PostgreSQL control/pgvector migrations、PyIceberg SqlCatalog、Iceberg warehouse FileIO、fsspec file/S3 adapters、operation ledger 和真实后端集成测试。
- 一套 DatasetManager Backend 使用 PostgreSQL、Iceberg Catalog 和 Warehouse 承载多个 Repo；每个 Repo 使用独立 Iceberg Namespace，所有 Repo 级 PostgreSQL 记录通过不可变 `repo_id` 隔离。
- 现有 `image_gallery.dataset`、`image_gallery.storage`、Import/Export、Cleaning、Visualization、Notebook 和 operators 不在本 change 中迁移，也不限制新 API 设计。
