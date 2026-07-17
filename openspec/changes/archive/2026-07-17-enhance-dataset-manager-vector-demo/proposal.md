## Why

现有 DatasetManager 综合 Notebook 只用单个代码单元展示向量生成，用户无法从示例中理解模型冻结绑定、增量跳过、覆盖生成、精确 View 范围、Snapshot 不变和重连恢复等新增契约。需要在同一生命周期演示中补齐这些关键行为，让示例既可教学也可作为真实 Backend 验收入口。

## What Changes

- 扩充现有中文 DatasetManager Notebook 的模型托管向量章节，不新增第二个示例文件。
- 展示冻结模型定义、VectorField 强绑定以及普通列与向量列的统一 DataFrame 读取。
- 演示默认 Head 生成、重复调用跳过、覆盖生成和指定 View 生成。
- 验证向量生成不推进 Iceberg Snapshot，并在关闭重连后恢复模型定义、字段和向量。
- 扩充 Notebook 自动化测试，确保新增演示在真实 PostgreSQL/pgvector、PyIceberg 和 MinIO Backend 上可执行。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `dataset-manager-demo`: 扩充综合 Notebook 对模型托管向量生成完整行为的演示和真实 Backend 验收要求。

## Impact

主要影响 `examples/dataset_manager_demo/dataset_manager_demo.ipynb`、对应中文说明和 Notebook 单元/集成测试；不修改 DatasetManager 公共 API、不新增运行时依赖，也不改变示例 Backend 配置方式。
