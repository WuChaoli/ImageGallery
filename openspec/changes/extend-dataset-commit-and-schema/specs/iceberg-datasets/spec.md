## MODIFIED Requirements

### Requirement: 固定系统字段与开放物理 Schema
每张 Dataset Table SHALL 包含 required `asset_id`、`storage_prefix_id`、`relative_path`，optional `source_uri` 和 required `tag_ids: list<string>`；Dataset SHALL 通过 `dataset.schema` facade 以 typed `ColumnSpec` 读取全部物理列并新增顶层可选业务列。业务列 SHALL 使用 DatasetManager 公共递归类型 DTO 表达受支持标量、List 和 Struct，DTO SHALL NOT 要求调用方提供 PyIceberg field ID。普通列与所属 Repo VectorField SHALL 共享去除首尾空白且大小写不敏感的名称空间，并 SHALL 在同一 Repo Schema 锁内重新检查后新增。

#### Scenario: 通过 Schema facade 新增标量普通列
- **WHEN** 调用方执行 `dataset.schema.add_column(...)` 且名称和标量类型有效
- **THEN** 新可选业务列加入 Dataset Table 并可由 View 读取，既有字符串标量类型输入被归一化为公共标量 DTO

#### Scenario: 新增 typed list struct 列
- **WHEN** 调用方以公共 DTO 新增元素为固定 Struct 的 List 业务列并提交符合结构的值
- **THEN** DatasetManager 内部分配全部 Iceberg field ID，值通过 Arrow、Snapshot、Checkpoint 和 Clone 保持相同嵌套结构

#### Scenario: 读取 typed 物理 Schema
- **WHEN** 调用方 list/get Dataset Schema，或在重开 Backend、Checkpoint、Branch、Clone、materialize 后读取 Schema
- **THEN** 返回按物理声明顺序排列且包含系统列的 `ColumnSpec`，递归类型与 required 信息保持一致且不暴露 Iceberg field ID

#### Scenario: 拒绝无效嵌套值
- **WHEN** 提交的 List/Struct 值缺少 required 子字段、包含未知子字段或类型不匹配
- **THEN** 整个写入在候选 Snapshot 产生前失败且 Branch Head 不变

#### Scenario: 嵌套值规范化后写入 durable intent
- **WHEN** 合法嵌套值包含 None、空 List、缺失 optional 子字段或 NumPy 标量
- **THEN** 系统在创建 operation 前产生 JSON-safe canonical value，SQLite/PostgreSQL journal 与 Arrow round-trip 保持相同 null、顺序和值语义

#### Scenario: 选择普通列和向量字段
- **WHEN** DatasetView.scan 的 fields 同时指定存在的物理列和所属 Repo VectorField
- **THEN** 返回精确字段投影且不隐藏系统列或改变字段顺序

#### Scenario: 拒绝破坏性 Schema 演进
- **WHEN** 请求 drop、rename、change-type、修改系统字段、修改嵌套字段或创建与 VectorField 同名的普通列
- **THEN** 操作失败且 Branch Head 不变

#### Scenario: 同 Repo Schema 修改互斥
- **WHEN** 多个调用方并发修改同一 Repo 中不同 Dataset 的普通列或 VectorField
- **THEN** 系统按 Repo 串行执行检查与修改，异常退出后锁可释放并允许后续修改

#### Scenario: 独立 add_column 使用 durable history operation
- **WHEN** 调用方通过 DatasetSchema.add_column 新增业务列
- **THEN** 操作按 Repo Schema lock、Dataset history lock 的固定顺序执行，并使用与 Commit schema additions 相同的 pending gate、可见性和 recovery 协议

#### Scenario: 不同 Repo Schema 修改独立
- **WHEN** 两个调用方并发修改不同 Repo 的 Schema
- **THEN** 两个 Repo 使用不同锁域且不因全局互斥而相互阻塞

### Requirement: Dataset Commit 使用完整行 upsert
Dataset SHALL 仅在显式 `mode="upsert"` 时按 `asset_id` 写入完整普通 Iceberg 行并保留未出现的既有行；仅在显式 `mode="patch"` 时使用 `fields` patch 已有行。已有 ID 的完整 upsert SHALL 使用完整规范化行替换，逻辑无变化时不得产生新 Snapshot。Commit MAY 携带显式顶层可选 `schema_additions`，并 SHALL 在同一可恢复发布中应用 Schema 与数据。

#### Scenario: Patch 已有行
- **WHEN** frame 包含已有 asset_id、`mode="patch"` 且 fields 只列出部分普通业务字段
- **THEN** 仅指定字段更新，其他字段保持基线 View 中的值

#### Scenario: 拒绝 Patch 新行
- **WHEN** `mode="patch"` 的 frame 包含基线 View 不存在的 asset_id
- **THEN** 整批 Commit 在写入前失败且 Branch Head 不变

#### Scenario: 新增和完整更新行
- **WHEN** `mode="upsert"` 的 frame 同时包含新 ID 与已有 ID 的完整普通字段
- **THEN** 新 ID 插入、已有 ID 完整替换、未出现旧行保留，并通过一次候选 Snapshot 发布

#### Scenario: 拒绝模式与 fields 冲突
- **WHEN** replace/upsert 携带 fields，或 patch 未携带非空 fields
- **THEN** Commit 在写入前失败并说明模式约束

#### Scenario: 拒绝直接提交向量
- **WHEN** fields 或 frame 包含所属 Repo 的 VectorField 名称
- **THEN** Commit 在写入前失败并指引调用 `dataset.generate_embed()`，Branch 和 Repo 当前向量均不改变

#### Scenario: No-op Commit
- **WHEN** 规范化后目标普通行、Schema 和 tag_ids 均无变化且未请求新 Checkpoint
- **THEN** Commit 返回 no-op，Branch 和 Snapshot 列表不变

#### Scenario: Commit 结果计数
- **WHEN** Commit 比较基线与最终规范化状态
- **THEN** 结果分别返回新增 ID、值变化的既有 ID 和 replace 移除 ID 的 inserted、updated、removed 计数，未变化重提行不计数

## ADDED Requirements

### Requirement: Dataset Commit 默认 replace 完整状态
Dataset SHALL 以 `mode="replace"` 作为默认 Commit 模式，把 frame 视为目标 Branch 的完整物理状态，并通过显式基线和候选 Snapshot 原子替换 Branch Head。

#### Scenario: Replace 移除未出现行
- **WHEN** 基线 View 有 100 行且 replace frame 只包含其中 80 个 asset_id
- **THEN** 新 Branch Head 只包含 80 行，既有固定 View 和 Checkpoint 仍读取原 100 行及其 tag_ids

#### Scenario: Replace 为空 Dataset
- **WHEN** 非空 Branch 使用具有目标 Schema 列的空 DataFrame 执行 replace
- **THEN** 新 Branch Head 是可读取的空 Snapshot，且旧 Snapshot 保持可读

#### Scenario: Replace No-op
- **WHEN** replace frame 规范化后与基线完整状态相同且未请求新 Checkpoint
- **THEN** 返回 changed=False 且不创建新 Snapshot

#### Scenario: Replace 不清理外部状态
- **WHEN** replace 从新 Head 移除一个 asset_id
- **THEN** 系统不删除其 Storage bytes、Repo Tag Definition、Repo 当前向量或旧 Snapshot 数据

### Requirement: Dataset Commit 组合顶层 Schema additions
Dataset Commit SHALL 支持显式新增顶层 optional `ColumnSpec`，并 SHALL 将 Schema update、规范化数据、Branch 发布与可选 Checkpoint 放入同一 durable operation；List/Struct 创建后其递归结构、顺序、required 与类型 SHALL 冻结。

#### Scenario: 新列与数据一起发布
- **WHEN** Commit 同时新增评估列或参数列并为其提交合法值
- **THEN** 普通 API 在 operation finalize 后同时看到新 typed Column、最终 Branch 数据与可选 Checkpoint，不观察到可见 Schema 但数据未发布的中间结果

#### Scenario: 拒绝修改嵌套结构
- **WHEN** 调用方请求向既有 Struct 增加子字段，或修改既有 List/Struct 的顺序、required 或类型
- **THEN** 操作在 Iceberg 或控制面副作用前失败

### Requirement: Dataset Schema 支持 Annotation v1 所需结构
Dataset 公共递归类型 SHALL 能表达物理 `annotations` 列的 `list<struct<label:string, bbox:struct<x_min:double, y_min:double, x_max:double, y_max:double>, format:string, source:string?, difficult:integer?, truncated:integer?, pose:string?>>` 且 List element required；Annotation v1 SHALL 是逻辑契约版本而非带点号的列路径，DatasetManager SHALL NOT 依赖 Annotation 模块或接受任意 JSON object 代替 typed 结构。

#### Scenario: Annotation v1 Round-trip
- **WHEN** Dataset 新增 `annotations` 列并提交零个或多个现有 `voc_bbox_to_annotation()` 兼容值
- **THEN** 当前 View、Checkpoint、Branch 和同 Repo 物化 Dataset 返回相同顺序、标签、嵌套 bbox、格式、来源、标志与 pose

### Requirement: Repo 可原子物化固定 View 的新 Dataset
DatasetRepo SHALL 支持从同 Repo 固定 DatasetView 的行 Snapshot、operation 开始时冻结的来源 Dataset 当前 Table Schema、显式附加字段和完整目标 frame 创建新 Dataset，并 SHALL 在 Table、Schema、首个 Snapshot、可选 Checkpoint 与控制面登记全部完成前保持目标 Dataset 不可见。

#### Scenario: 物化筛选结果
- **WHEN** 调用方从固定 View 提交其部分 asset_id 的完整 frame 和新 Dataset 名
- **THEN** 新 Dataset 只包含该 frame，复用图片位置和内容身份，不继承源历史、Branch、Checkpoint 或 Repo 当前向量副本

#### Scenario: 物化空结果并创建 Checkpoint
- **WHEN** 完整目标 frame 为空且请求初始 Checkpoint
- **THEN** 新 Dataset 具有可读取的空 Snapshot，main 与初始 Checkpoint 指向该 Snapshot

#### Scenario: 中断后恢复物化
- **WHEN** Table 或候选 Snapshot 已创建但控制面尚未 finalize 时进程中断
- **THEN** 普通 list/open API 不暴露目标 Dataset，recover_operations 幂等完成相同 Schema、行、main 与可选 Checkpoint

#### Scenario: 拒绝跨 Repo 物化
- **WHEN** 目标 Repo 与来源 DatasetView 不属于同一 Repo
- **THEN** 操作在创建 Table 或写入行前失败

### Requirement: DatasetView 可导航所属句柄
固定 DatasetView SHALL 公开返回同一 Backend 中按不可变 ID 解析的所属 Dataset 与 DatasetRepo 句柄，不要求消费者访问私有 manager。

#### Scenario: 从 View 定位默认发布目标
- **WHEN** 调用方从有效固定 View 读取其 Dataset 和 Repo owner
- **THEN** 返回的句柄与 View 的 repo_id/dataset_id 一致，并可用于 commit、create_branch 或 materialize_dataset

#### Scenario: 拒绝失效或伪造 View owner
- **WHEN** View 所属控制面对象不可见，或 View 被另一个 Manager 伪造使用
- **THEN** owner 导航稳定失败且不返回错误 Backend 的句柄
