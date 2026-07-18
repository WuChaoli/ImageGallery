## Why

`DatasetManager` 当前同时承担连接生命周期、数据集历史协议、候选 Snapshot 发布和 durable operation 恢复，导致 `manager.py` 过长且历史事务语义难以独立审查。需要在不改变任何公开接口或持久化行为的前提下，把这组高耦合职责收敛到窄私有协作模块。

## What Changes

- 用特征测试固定 commit、clone、checkpoint、branch、rollback、候选发布、pending vector 和恢复的现有语义。
- 将 Dataset 历史操作、Iceberg ref 发布和 durable recovery 从 `DatasetManager` 拆入私有协作模块。
- 保持公开导出、方法签名、异常类型、operation hook 时序、控制面事务以及 Iceberg ref 行为不变。
- 不修改 Tag、VectorField、embed 或 DatasetView IO 职责。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `dataset-versioning`: 增加内部历史职责拆分后必须保持全部公开、持久化、异常和恢复语义不变的约束。

## Impact

- 影响 `src/image_gallery/dataset_manager/manager.py` 及新增的 DatasetManager 私有历史协作模块。
- 增加 DatasetManager 历史边界和恢复协议特征测试。
- 不增加依赖，不改变公开 API、数据库 Schema 或 OpenSpec 产品行为。
