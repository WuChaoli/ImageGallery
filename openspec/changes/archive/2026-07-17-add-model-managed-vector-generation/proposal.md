## Why

当前 VectorField 要求调用方直接生成并提交向量及验证集输出，既暴露了不必要的底层写入入口，也无法保证字段始终由冻结的模型配置生成。需要把模型生命周期纳入 DatasetManager 基础设施，并将向量生成收束为针对精确 DatasetView 的受控操作。

## What Changes

- 新增 ModelManager，负责持久化稳定 `model_id` 的冻结模型配置、管理模型运行时与资源生命周期，并为 DatasetManager 提供受控推理能力。
- VectorField 在创建时强绑定已注册模型的身份、配置指纹、维度和数值类型，创建后不可修改。
- 新增 `Dataset.generate_embed(field=..., source=None, branch="main")`：默认在调用开始时固定 `main` 当前 Head 并处理其中全部行，也可指定 Branch Head 或当前 Dataset 的精确 DatasetView；本轮不支持全 Repo 生成。
- 将 Model 和 Storage Prefix 的非敏感冻结定义持久化到 PostgreSQL control schema，进程恢复时自动还原相同 `model_id` / `prefix_id` 的原定义；凭证仍只保存外部引用。
- `DatasetView.scan()`、`get_rows()` 和 `get_row()` 统一通过 `fields` 选择普通列或向量字段，并返回 pandas DataFrame/Series。
- `Dataset.commit(frame=..., fields=...)` 使用 DataFrame：显式 `fields` 表示 patch，未传表示普通物理列的完整 upsert。
- **BREAKING**：Dataset Commit 与公开 VectorField API 不再接受调用方生成的向量、validation outputs 或组合 Data+Vector 提交；向量只能通过 `generate_embed()` 生成。
- **BREAKING**：移除冻结验证集及其持久化契约，以模型强绑定和生成时的基础维度、类型、有限值校验取代。
- **BREAKING**：Schema 演进收束到 `dataset.schema.add_column(...)` 与 `repo.schema.add_vector(...)` facade，不保留旧直接入口的兼容层。

## Capabilities

### New Capabilities

- `model-manager`: 定义模型持久化注册、冻结身份、恢复、运行时解析、推理调用和资源释放契约。

### Modified Capabilities

- `iceberg-datasets`: 调整 Schema facade、DataFrame 读取与普通列 patch/full commit 行为，并禁止 Commit 直接写向量。
- `repository-vectors`: 以冻结模型绑定和 Dataset 级 `generate_embed()` 替换验证集及调用方向量写入契约。

## Impact

- 影响 DatasetManager、DatasetRepo、Dataset、DatasetView、VectorField、PostgreSQL/pgvector 元数据模型及 Alembic 初始迁移。
- 新增模型 provider/runtime 抽象与持久化 Model/Storage 定义，并由 DatasetManager 与 StorageManager 协同完成可信图片读取和批量推理。
- 需要删除验证集相关 DTO、表和测试，更新公开导出、Notebook 示例与 E2E 测试。
- 不改变 Iceberg Snapshot 的历史语义；向量仍是 Repo 级当前值，生成向量不会推进 Dataset Branch、Snapshot 或 Checkpoint。
