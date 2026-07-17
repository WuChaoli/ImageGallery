## Context

现有 DatasetManager 已把 Dataset 历史放在 Iceberg、Repo 当前向量放在 PostgreSQL/pgvector，并通过 StorageManager 解析图片位置。当前向量写入仍由调用方提供向量和 validation outputs，Dataset Commit 还可组合发布数据与向量。这使模型身份无法真正约束向量来源，也让常规 Dataset 写入承担了模型协议。

本次变更跨越模型运行时、Schema、Dataset IO、Repo 向量存储和示例。仓库仍处于开发阶段，因此直接修订初始数据模型与公开 API，不提供旧接口兼容层。

## Goals / Non-Goals

**Goals:**

- 让每个 VectorField 强绑定一个已注册、配置冻结的模型。
- 让 `Dataset.generate_embed()` 成为唯一公开向量生成与写入入口。
- 默认处理 `main` 当前 Head 的全部行，也允许指定 Branch Head 或精确 DatasetView；执行前始终固定为一个 Snapshot。
- 持久化 Model 和 Storage Prefix 的冻结非敏感定义，使进程恢复后稳定 ID 自动指回原定义。
- 统一普通列和向量字段的 DataFrame 读取体验，同时保持二者不同的历史语义可见。
- 让 Dataset Commit 只处理普通 Iceberg 字段，并清晰区分 patch 与完整 upsert。

**Non-Goals:**

- 不支持整个 Repo 扫描、所有 Branch/历史 Snapshot 并集、跨 Dataset 去重调度或后台 embedding 任务。
- 不保存向量历史，也不让 Vector-only 更新推进 Iceberg Snapshot。
- 不提供模型训练、模型文件分发、远程模型服务治理或通用 MLOps 能力。
- 不保留 validation set、validation outputs、调用方向量写入或 Data+Vector 组合提交。

## Decisions

### 1. ModelManager 是 DatasetManager 的基础设施依赖

DatasetManager 组合 ModelManager 与 StorageManager。两者的冻结非敏感定义由 PostgreSQL control schema 持久化，进程启动后自动恢复 `model_id -> ModelDefinition` 和 `prefix_id -> StoragePrefix`；provider runtime、GPU session、filesystem client 等资源仍按需加载并只存在于进程内。

模型定义保存 provider、artifact URI/revision/checksum、非敏感配置、维度、dtype、credential reference 和稳定指纹；Prefix 定义保存 backend、规范化 root、endpoint、credential reference 和稳定指纹。明文凭证只由 CredentialProvider 运行时解析，不进入数据库、指纹、DTO 或日志。同一稳定 ID 与相同定义幂等，异定义拒绝。

备选方案是把 `embed(frame)` 放在 ModelManager 或模型句柄上公开给调用方；这仍允许绕过 DatasetRepo 的成员、Storage 和发布边界，因此不采用。

### 2. VectorField 冻结模型快照而不是验证集

`repo.schema.add_vector(name, model_id, distance)` 必须先解析已注册模型，并把 `model_id`、配置指纹、输出维度、dtype 和距离度量原子持久化到 VectorField。已存在同名字段仅在定义完全一致时幂等返回，否则拒绝。

生成时 ModelManager 当前注册定义的指纹必须与字段冻结值一致。这样即使进程重启或注册顺序变化，也不能用同一 ID 的另一配置生成该字段。基础输出校验只检查批量数量、维度、dtype 可转换性和有限值。

### 3. generate_embed 属于 Dataset 并在开始时固定 View

公开签名以 `dataset.generate_embed(field=..., source=None, branch="main", overwrite=False)` 为核心。未传 source 时，系统在调用开始瞬间打开 branch 当前 Head（默认 main）并固定为精确 View；传入 source 时必须属于当前 Dataset，且不得同时指定非默认 branch。后续成员枚举和图片读取始终使用该固定 Snapshot，并在结果中返回实际 `source_snapshot_id`。

推理可以内部批处理以控制内存，但本次请求的向量只在全部读取、推理和校验成功后通过一个 PostgreSQL transaction 发布。失败不产生部分新值。`overwrite=False` 跳过已有 Repo 当前值，`overwrite=True` 重新生成并替换；返回 generated、updated、skipped 计数。

全 Repo、全部 Branch 或全部历史 Snapshot 的并集生成需要额外定义资产枚举、位置冲突和失败恢复，本轮刻意不设计。

### 4. 读取统一 fields，存储语义保持显式

`DatasetView.scan(fields=...)`、`get_rows(..., fields=...)` 和 `get_row(..., fields=...)` 先由 Schema facade 将名字解析为 Iceberg 物理列或 Repo VectorField。物理列从 View 固定 Snapshot 读取；向量以一条批量查询合并 Repo 当前值，缺失值为 `None`，禁止 N+1 查询。

未传 `fields` 时只返回全部物理列，不隐式加载可能昂贵的向量。`scan`/`get_rows` 返回 DataFrame，`get_row` 返回 Series；顺序遵循 View 的稳定扫描顺序。

### 5. Commit 只接受普通列 DataFrame

`dataset.commit(frame=..., fields=[...])` 的显式 fields 表示按 `asset_id` patch 指定普通字段，未传 fields 表示 frame 中普通物理字段的完整行 upsert。两种模式都执行系统字段、Schema、asset_id、Storage 位置和 tag_ids 校验。

任何注册 VectorField 名出现在 fields 或 frame 中均立即拒绝，并提示使用 `dataset.generate_embed()`。这消除 Dataset 与 pgvector 的跨存储组合发布协议。

### 6. Schema 修改只通过 facade

Dataset 暴露 `dataset.schema.add_column/get_column/list_columns`，Repo 暴露 `repo.schema.add_vector/get_vector/list_vectors`。Facade 负责名称冲突检查：普通列与 Repo VectorField 不得同名。旧直接入口删除，不设置 deprecated shim。

## Risks / Trade-offs

- [Repo 当前向量会让旧 View 看到新 embedding] → 文档和测试明确固定 Snapshot 只适用于物理行，向量是 Repo 当前值。
- [一次请求原子发布可能占用较多内存] → 推理分批执行、结果暂存到有界结构；MVP 优先保证无部分发布，超大任务留待后台任务设计。
- [持久化定义指向的模型文件或 Backend 离线不可达] → 保留冻结定义并返回明确的资源不可用错误，禁止静默改绑；完整离线恢复必须同时恢复数据库、warehouse、模型 artifact 和 Storage 数据。
- [直接修订初始迁移会破坏已有开发数据库] → 明确开发期重建数据库流程，Notebook 同时提供复用可连接 `.env` 和重新创建数据库的指引。
- [同 asset_id 在不同 Dataset Snapshot 可能指向不同位置] → 默认 Head 或显式来源都先固定为精确 View，只读取该 View 的位置，不做 Repo 级位置推断。

## Migration Plan

1. 删除 validation set/output DTO、表、控制元数据和组合提交代码，修订初始 Alembic 迁移。
2. 引入 ModelManager、持久化 Model/Storage 定义与测试 provider，再将其注入 DatasetManager。
3. 增加 Schema facade、DataFrame IO 与仅普通列 Commit。
4. 实现 Dataset 默认 main Head、可选 Branch/View 的 `generate_embed()` 与 pgvector 原子发布。
5. 更新 E2E、Notebook、README/AGENTS 导航并重建开发数据库验证。

回滚通过回退本变更并重新创建开发数据库完成；不承诺迁移已有实验数据。

## Open Questions

- 无。本轮已明确不支持全 Repo embedding；后续需单独 OpenSpec 设计资产枚举、调度和恢复语义。
