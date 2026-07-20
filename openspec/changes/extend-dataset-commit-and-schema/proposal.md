## Why

DatasetManager 当前只提供完整行 upsert/patch、Checkpoint-only 分支来源和基础标量业务列，无法安全承载清洗结果的 replace 发布、带公开历史标签的原子提交、无标签实验 Branch，以及 typed annotation 等嵌套数据。后续 Importer、Cleaning、Visualization 与 Annotation 适配必须先建立一致、可恢复且不泄漏下游领域概念的 Dataset 基础契约。

## What Changes

- **BREAKING**：`Dataset.commit()` 默认把输入 frame 视为目标 Branch 的完整状态并执行 replace；调用方必须显式选择 `upsert` 或 `patch` 才保留未提交行。
- 为 `Dataset.commit()` 定义显式 `replace`、`upsert`、`patch` 模式及各自的 frame/fields 校验规则，并返回 inserted、updated、removed 计数。
- 允许一次 Dataset Commit 携带可选 Checkpoint 名称，使候选 Snapshot 发布与 Checkpoint 创建共享 durable operation；不指定名称时只推进 Branch。
- 允许 Commit 同时携带显式顶层 Schema additions，使新增评估列、参数列或 Annotation 列与数据、Branch 和可选 Checkpoint 共享可恢复发布协议。
- 允许 Branch 从同 Dataset 的任意固定 `DatasetView` 创建，不再要求来源必须先成为 Checkpoint。
- 扩展 Dataset 业务 Schema，使其通过通用类型 DTO 双向描述基础标量、`list` 与 `struct`，并支持现有 Annotation v1 所需的 typed `list<struct>`，但 DatasetManager 不依赖 Annotation 领域模块。
- 为固定 `DatasetView` 提供公开、类型安全的所属 Dataset 与 Repo 导航，使后续消费者无需访问私有 `_manager` 即可选择原 Branch、新 Branch 或新 Dataset 目标。
- 提供同 Repo 内从固定 View 的 Schema 与显式 frame 原子创建新 Dataset 的基础操作；新 Dataset 不继承源历史、Branch、Checkpoint 或向量，只复用图片位置和内容身份。
- 保持旧 Snapshot、Checkpoint 中被 replace 移除的行及其 `tag_ids` 可读；replace 不删除 Tag Definition、图片 bytes 或 Repo 当前向量。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `iceberg-datasets`: 修改 Dataset Commit 默认写入语义，增加显式模式、通用嵌套 Schema，以及从固定 View 原子物化新 Dataset 的行为。
- `dataset-versioning`: 增加 Commit 与 Checkpoint 的可恢复组合语义，并允许从任意同 Dataset 固定 View 创建 Branch。
- `dataset-repositories`: 扩展 Repo 创建 Dataset 的 durable 生命周期，使基于固定 View 与显式 frame 的新 Dataset 在完整发布前不可见。

## Impact

- 公共 API：`Dataset.commit()`、`DatasetSchema` typed introspection、`DatasetView` owner 导航、`Dataset.create_branch()`、`DatasetRepo` 的新 Dataset 物化入口与相关返回 DTO。
- 持久化与恢复：Dataset operation intent、phase、recovery、Iceberg candidate ref/Branch/Tag 发布顺序。
- Schema：PyIceberg 标量、List 与 Struct 类型构造、DataFrame/Arrow 规范化和跨 Snapshot/Clone 读取。
- 测试：`tests/unit/dataset_manager/` 与 `tests/integration/dataset_manager/`，并继续通过独立 `dataset-backend` 入口验证 PostgreSQL、PyIceberg 和 S3-compatible Backend。
- 后续 change：Importer、Cleaning、Operators、Visualization 与 Annotations 将依赖本 change 的已归档契约，本 change 不直接修改这些消费者的公开 API。
