## Why

`dataset_manager/manager.py` 目前约 1560 行，同时承担 Backend 生命周期、Repo/Dataset 控制面、Storage Prefix 授权、durable operation 日志以及版本、向量和读取逻辑。公开门面与控制面细节混在同一类中，使后续历史协议和向量能力无法在不扩大回归面的前提下继续简化。需要先固定生命周期语义，并把 Repo/Dataset 控制面与 operation journal 收敛为私有协作对象。

## What Changes

- 补充 DatasetManager 资源所有权、Repo/Dataset 可见性、Prefix 恢复和 operation 状态转换的 characterization tests。
- 将 Repo/Dataset 元数据查询、创建登记、名称冲突与 Storage Prefix 绑定提取到私有 repository 协作模块。
- 将 durable operation 的创建、intent 更新、阶段记录、完成和失败状态更新提取到私有 operation journal。
- 保留 `DatasetManager` 公开构造、factory、context manager、Repo/Dataset handle、异常和持久化 schema 语义不变。
- 不修改 commit、clone、checkpoint、rollback、Tag、VectorField 或 embedding 算法；这些能力只改为使用窄化后的内部边界。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `dataset-repositories`: 明确 DatasetManager 内部职责拆分后 Backend/Repo/Dataset 生命周期、资源所有权与 Prefix 授权语义保持不变。
- `iceberg-datasets`: 明确 Dataset 原子创建及 durable operation 可见性、恢复和失败状态语义保持不变。

## Impact

- 影响 `src/image_gallery/dataset_manager/manager.py`、新增的模块私有控制面协作文件，以及 `tests/unit/dataset_manager/`。
- 不新增公共导出，不修改 Alembic、Iceberg 或 PostgreSQL schema，不要求调用方迁移。
- 必须通过默认测试、90% 全仓覆盖率、`test-all` 与 `dataset-backend`，并保持公开接口契约测试全绿。
