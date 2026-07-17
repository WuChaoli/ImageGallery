## Why

DatasetManager 的核心能力目前分别由单元测试和一个部分真实后端测试覆盖，但缺少一条从真实图片来源进入、经过存储、版本迭代、分支分叉、回退和重启重开的完整用户旅程。现有 E2E 直接构造行，无法证明来源解析、StorageManager、Iceberg 历史和 PostgreSQL 控制面能够作为一个生命周期稳定协作。

## What Changes

- 新增仅供测试使用的 DatasetManager Importer，复用现有 `SourceParser`/`SourceRecord`，但不进入 `src/`、不导出为正式 API，也不改变现有 ImportPipeline。
- 新增真实 PostgreSQL、pgvector、PyIceberg Warehouse、file/MinIO StorageManager 上的完整 Dataset 生命周期 E2E。
- E2E 从隔离的真实图片目录导入，验证托管存储、内容哈希身份、读取、多轮 commit、Checkpoint、Branch 独立演进、固定 View、rollback、Clone、Tag、Vector、冲突和 Manager 重启重开。
- 收敛真实后端测试的资源生命周期和诊断边界，使测试能够在成功与失败后正常退出，并为慢容器启动提供可定位的阶段证据。
- 补齐已有 Vector 验证集与组合提交测试矩阵中缺少的乱序、容差、Inf 和组合提交 Branch CAS 冲突用例。
- 不把旧 Importer 迁移到 DatasetManager；正式 Importer 的产品 API、失败清单、重试和批处理策略留给后续 change。

## Capabilities

### New Capabilities

- `dataset-manager-lifecycle-testing`: 规定测试专用导入边界和 DatasetManager 真实后端完整生命周期验收要求。

### Modified Capabilities

- `repository-vectors`: 补充 VectorField 验证集边界与 Data+Vector 组合提交并发冲突的可验证要求，不改变生产 API 语义。

## Impact

- 新增 `tests/helpers/` 下的测试专用 DatasetManager Importer 与结果 DTO。
- 扩展 `tests/integration/dataset_manager/` 的真实后端测试及 fixtures，并补充 `tests/unit/dataset_manager/` 的向量边界测试。
- 使用现有 testcontainers、PostgreSQL/pgvector、PyIceberg、file 与 MinIO 依赖，不增加生产依赖。
- `src/image_gallery/importers/`、旧 Dataset/Storage 和新 DatasetManager 公共 API 均不发生兼容性变更。
