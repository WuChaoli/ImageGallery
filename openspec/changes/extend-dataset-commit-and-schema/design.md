## Context

DatasetManager 当前把 Dataset 行、Schema、Tag Assignment 与 Snapshot 历史保存在每 Dataset 单 Iceberg Table，把 Repo/Tag Definition/VectorField/当前向量与 durable operation 保存在控制数据库。`Dataset.commit()` 目前通过是否传入 `fields` 区分完整行 upsert 与 patch，Branch 只能从 Checkpoint 创建，业务 Schema 只暴露五种标量字符串类型。

后续 Cleaning 需要把筛选结果作为 Branch 的完整新状态发布，并可选择为新 Snapshot 创建公开历史 Checkpoint；Importer 仍需要增量 upsert；Annotation 需要 typed `list<struct>`。这些消费者不能各自实现 Iceberg overwrite、ref 发布、字段 ID 或故障恢复，因此基础语义必须收敛在 DatasetManager。

## Goals / Non-Goals

**Goals:**

- 让 Commit 模式显式、可验证，并以 replace 作为默认完整状态发布语义。
- 让显式 Schema additions、Branch Snapshot 发布与可选 Checkpoint 创建共享 durable operation 和恢复协议。
- 允许从同 Dataset 任意固定 View 零拷贝创建 Branch，而不强制创建 Checkpoint。
- 用不泄漏 PyIceberg 实现的公共 DTO 双向表达标量、List 和 Struct 业务类型。
- 让 DatasetView 可公开导航到所属 Dataset 与 Repo，支持下游基于来源 View 选择发布目标。
- 原子物化同 Repo 新 Dataset，使 Schema、行、首个 Snapshot 与可选 Checkpoint 完成前对普通 API 不可见。
- 保留历史 Snapshot、Tag Assignment、Storage bytes、Tag Definition 和 Repo 当前向量的既有所有权边界。

**Non-Goals:**

- 不在本 change 修改 Importer、Cleaning、Operator、Visualization 或 Annotation 的公开 API。
- 不提供删除、retention、Snapshot expiry、GC、merge、diff、rebase 或跨 Repo clone/materialize。
- 不把 Repo 当前向量写入 Iceberg，也不随 replace 清理向量或图片 bytes。
- 不支持任意 Python object、JSON blob、Map 或无 Schema 动态字段。

## Decisions

### 1. Commit 使用显式模式，replace 为默认值

新增公开 `CommitMode`，取值为 `replace`、`upsert`、`patch`：

- `replace`：默认模式。输入 frame 是目标 Branch 的完整物理状态；未出现的旧 `asset_id` 从新 Snapshot 消失。`fields` 必须为空。
- `upsert`：输入是完整规范化行；相同 `asset_id` 替换，新增 ID 插入，未出现旧行保留。`fields` 必须为空。
- `patch`：`fields` 必须是非空普通字段集合；frame 必须携带 `asset_id` 且只能更新基线 View 已存在的行。

replace 接受具有目标 Schema 列的空 DataFrame，并可把非空 Branch 发布为空 Snapshot。三种模式都先完成 Repo、Dataset、Branch、Schema、Storage Prefix、内容身份、Tag Assignment、VectorField 禁止写入和重复 `asset_id` 校验，再产生候选 Snapshot。规范化后逻辑无变化时不创建新 Snapshot。

`CommitResult` 返回 `inserted`、`updated`、`removed` 与 `changed`。计数以基线和最终规范化物理状态比较：新增 ID 计入 inserted，保留但至少一个值变化的 ID 计入 updated，只在 replace 中消失的 ID 计入 removed；重复提交但值未变的行不计数。Schema-only 变化使 `changed=True`，但不虚构行计数。

替代方案是继续通过 `fields is None` 推断模式，但它无法区分 replace 与 upsert，也会让调用方在默认值变更后难以审计，因此拒绝。

### 2. 可选 Checkpoint 是 Commit durable intent 的一部分

`Dataset.commit(..., schema_additions: Sequence[ColumnSpec] = (), checkpoint_name: str | None = None)` 把显式顶层可选列、新数据状态和可选 Checkpoint 名称写入同一 operation intent。Schema update 与候选数据 Snapshot 通过同一 Iceberg transaction 提交；普通 open/list/schema API 在 operation active 时返回 reconciling conflict，直到 Branch 与可选 Checkpoint 均完成并 finalize。返回 `CommitResult` 增加 `checkpoint: DatasetView | None`：

1. 在任何外部副作用前校验名称、同名 ref 和同 Dataset pending operation。
2. 生成并记录候选 Snapshot。
3. 以乐观并发校验发布目标 Branch。
4. 为最终 Snapshot 创建 Checkpoint。
5. 记录 `checkpoint_created` 并 finalize。

若 replace/upsert/patch 是数据 no-op，但指定了新 Checkpoint，系统直接为基线 Snapshot 创建 Checkpoint，`changed=False`。唯一例外是 snapshotless 空 Dataset 的 empty replace：请求 Checkpoint 时必须生成首个可读取空 Snapshot 作为版本锚点，再创建 Checkpoint，逻辑结果仍为 `changed=False`。未请求 Checkpoint 的 empty-to-empty replace 保持无 Snapshot no-op。

如果仅 Schema additions 产生变化，Schema 属于整个 Dataset Table，`changed=True`；未产生数据 Snapshot 时只能为已有基线 Snapshot 创建 Checkpoint。自动生成 Checkpoint 名称只属于后续 `Cleaner.commit()`：Dataset 层未传 `checkpoint_name` 时只发布 Schema/Branch，不创建公开历史。

同 Dataset 历史修改与其 recovery 使用同一锁域串行；获得锁后必须重新读取 operation status、pending 门禁、ref 与基线。PostgreSQL 使用 session advisory lock，本地 Backend 使用按 Backend identity 在同进程共享的锁注册表且不承诺 SQLite 跨进程写入；不同 Dataset 不互相阻塞。未完成 operation 存在时拒绝新的同 Dataset 历史操作，先由 `recover_operations()` 幂等补齐 Schema/Branch/Checkpoint。两个 recoverer 或 API 与 recovery 并发时只有持锁者执行恢复。系统只承诺协调 DatasetManager API 写入，不兼容绕过 API 直接修改 Catalog refs 的调用方。

operation active 时，普通 Branch Head、Checkpoint 打开/列表与 Schema discovery 不暴露部分结果。data/ref-only operation 不影响调用方已经持有的固定 View 读取其固定 Snapshot；包含 Schema additions 的 operation 会阻断既有 View 的默认 scan 及其他依赖当前 Table Schema 的 IO，避免新列在数据与 Checkpoint finalize 前以 null 提前出现。finalize 后新 Branch Head、Schema 与 Checkpoint 一起成为普通 API 的可见结果。

替代方案是在 Cleaner 中先 commit 再 create_checkpoint，但崩溃窗口会跨越两个独立 operation，无法可靠恢复，因此拒绝。

### 3. Branch 可直接从固定 DatasetView 创建

`Dataset.create_branch(name, source)` 接受同 Dataset 的 Branch View 或 Checkpoint View，只要求 `source.snapshot_id` 非空且 Snapshot 仍存在。创建的 Branch 直接指向该固定 Snapshot，不创建隐式 Checkpoint，不移动来源 ref。

Branch 名与任意既有 Iceberg ref 冲突时在副作用前失败。该操作继续进入 durable journal，并在中断后幂等恢复。

来源 Branch View 即使已不再是当前 Head，只要它固定的 Snapshot 仍存在，也可以作为新 Branch 起点。Branch ref 已创建但 operation 尚未 finalize 时，普通 ref API 按 reconciling 状态处理，recovery 不重复创建 ref。

替代方案是自动为 Branch View 创建隐藏 Checkpoint，但这会违反无标签保存语义并污染公开历史列表，因此拒绝。

### 4. 公共 Schema 使用通用递归 DTO

新增不可变公共 DTO，名称以最终实现为准但职责固定：

- `PrimitiveFieldType(name)`：仅接受 `boolean`、`double`、`integer`、`long`、`string`。
- `StructField(name, field_type, required=False)`：描述 Struct 子字段。
- `StructFieldType(fields)`：至少一个、名称大小写不敏感唯一的固定字段集合。
- `ListFieldType(element_type, element_required=False)`：描述固定元素类型。
- `ColumnSpec(name, field_type, required=False)`：公开描述顶层系统列或业务列；新增业务列必须 optional。

`DatasetSchema.add_column()` 与 Commit `schema_additions` 接受上述 DTO；`list_columns()`/`get_column()` 返回 typed `ColumnSpec`，包含系统列并保持物理声明顺序。独立 `add_column()` 不是绕过路径：它作为 schema-only durable history operation 使用与 Commit 相同的 pending gate、recovery 和可见性协议，同时持有 Repo Schema lock 与 Dataset history lock。所有同时需要两把锁的 API 与 recovery 一律先取 Repo Schema lock，再取 Dataset history lock，避免死锁。

为保持简单标量调用可读性，现有字符串标量输入可归一化为 `PrimitiveFieldType`。DTO 不接受 PyIceberg field ID：同一 Table 的既有 ID 保持稳定；新增字段由目标 Table 递归分配无冲突 ID；materialize 到新 Table 时重新分配目标 ID，durable intent 只保存 DTO。

本 change 只允许新增顶层 optional 业务列。List/Struct 创建后，其递归结构、顺序、required 与类型全部冻结，不提供嵌套 add/drop/rename/change-type。类型树必须有限且无环，允许 List 嵌套 List；Struct 子字段名去除首尾空白后非空、大小写不敏感唯一，并保持声明顺序。

写入前按 DTO 递归规范化为 JSON-safe canonical values：Struct 只接受 mapping、List 只接受 list；NumPy 标量转换为对应 Python 标量，`pd.NA` 与 NaN 只可归一化为空值，bool 不作为 integer，integer/long 检查范围。缺失 optional Struct 字段与显式 None 统一为空值，缺失 required 字段、未知字段、非法 element null 和隐式 Arrow 强转全部在 operation 创建前失败；null List 与空 List 保持不同。相同 canonical values 同时用于 durable intent 与 Arrow/Iceberg 写入。

Annotation v1 是逻辑契约版本，不是带点号的物理列路径；后续 Annotation change 可在物理 `annotations` 列定义 `list<struct<label, bbox:struct<x_min, y_min, x_max, y_max>, format, source, difficult, truncated, pose>>`。List element required；其中 label、bbox、format 与 bbox 坐标 required，其余字段 optional。DatasetManager 本身不导入 `image_gallery.annotations`。

替代方案是把 annotation 存为 JSON string，虽然实现简单，但会失去字段级类型、Arrow round-trip 和查询能力，因此拒绝。

### 5. 新 Dataset 物化由 Repo 领域操作原子完成

新增 `DatasetRepo.materialize_dataset()` 领域入口，接收同 Repo 固定 `source`、新 Dataset 名、完整目标 frame、可选附加 Schema DTO 和可选 Checkpoint 名称。固定 View 只固定行 Snapshot；由于 Schema 是 Dataset Table 级，operation 在 Repo Schema 锁内冻结来源 Dataset 当时的当前完整 `ColumnSpec` 到 intent。它：

- 复制 operation 开始时冻结的来源 Dataset 当前完整物理 Schema，再应用显式附加字段。
- 校验 frame 是目标 Dataset 的完整状态，允许空 frame。
- 创建独立 Table/main Branch 和首个可读取 Snapshot，不复制图片 bytes 或 Repo 当前向量；空 frame 也必须形成空 Snapshot，因此可创建初始 Checkpoint。
- 不继承来源 Branch、Checkpoint 或 Snapshot 历史。
- 在 Table、Schema、行、可选 Checkpoint 和控制面 registration 全部完成前，不向 list/open API 暴露新 Dataset。
- 通过 durable intent 在中断后幂等完成；同名 Dataset 的大小写不敏感冲突继续生效。

在任何 Catalog 副作用前，系统为 `(repo_id, normalized_target_name)` 建立 durable 名称预留；并发同名 loser 稳定失败，恢复期间预留继续有效。同名重试只可接管同一 operation，不能误删 winner；无法归属到有效 operation 的内部 Table 按既有不可见 orphan 策略保留供诊断，本 change 不新增公共删除 API。

该入口只允许同 Repo View，避免跨 Repo Prefix、Tag 和 VectorField 语义扩散。它返回包含新 `Dataset`、main `DatasetView` 与可选 Checkpoint View 的结果 DTO。

替代方案是消费者依次 create_dataset/add_column/commit/create_checkpoint，但任何中断都会留下可见的空 Dataset 或部分 Schema，因此拒绝。

### 6. DatasetView 提供公开 owner 导航

`DatasetView.dataset` 与 `DatasetView.repo` 返回由同一 DatasetManager Backend 打开的类型安全句柄。导航按不可变 repo_id/dataset_id 解析，不按可变名称猜测；来源已失效、跨 Manager 伪造或控制面对象不可见时稳定失败。该导航只解决归属定位，不把 commit、branch 或 materialize 方法复制到 View。

替代方案是让 Cleaner 接收额外 Dataset/Repo 参数，但默认提交到来源目标时会产生可不一致的重复身份，也会迫使所有 DatasetView 消费者访问私有 `_manager`，因此拒绝。

### 7. replace 只改变新 Snapshot 的行集合

replace 不删除旧 Snapshot 数据文件、Checkpoint、Repo Tag Definition、StorageManager managed objects 或 Repo 当前向量。被移除行及其 `tag_ids` 仍可由既有固定 View/Checkpoint 读取；当前 Branch Head 和从它创建的新 View 不再包含这些行。

本 change 不引入 Snapshot expiry 或 GC，因此旧数据的物理保留与现有 MVP 一致。

## Risks / Trade-offs

- [默认 replace 是 breaking change，旧调用方可能意外删除当前 Head 行] → 修改所有仓库内调用点和示例；Importer 等增量写入必须显式 `mode="upsert"`；用公共 API 契约测试锁定默认值。
- [Checkpoint 命名与并发 ref 修改产生竞态] → 同 Dataset 历史锁、pending operation 门禁、ref 预检与恢复测试共同约束；直接 Catalog 写入不在支持范围。
- [空 replace 在不同 PyIceberg Backend 上行为不同] → local 与 `dataset-backend` 都覆盖非空到空、空到空和恢复测试。
- [递归类型扩大 Arrow/Pandas 规范化复杂度] → 只支持 Primitive/List/Struct，进入 Iceberg 前做逐值结构校验，不接受任意 object/Map。
- [Schema 是 Table 级而非 Branch 级] → 文档明确任何 Branch 添加字段都会演进整个 Dataset Schema；需要隔离时显式 materialize 新 Dataset。
- [新 Dataset materialize 的 intent 体积可能随 frame 增长] → 沿用当前 MVP durable row intent 的边界；大规模 staging/manifest 优化不纳入本 change，并通过任务记录后续容量风险。

## Migration Plan

1. 先增加 CommitMode、递归 Schema DTO、返回 DTO 与失败用例，不改变持久层行为。
2. 扩展 durable operation intent/recovery 和同 Dataset 历史锁，再实现 replace 与可选 Checkpoint。
3. 放宽 Branch 来源并补齐 ref 恢复。
4. 实现 typed Schema introspection、嵌套规范化、Arrow/journal round-trip 和 Clone 保持。
5. 实现 `materialize_dataset()` 的不可见创建与恢复。
6. 更新仓库内 DatasetManager 调用点：需要增量行为者显式使用 upsert，需要字段 patch 者显式使用 patch。
7. 依次运行默认测试和独立 Dataset Backend 验收；验证通过后再允许后续消费者 change 开始。

若部署后需要回滚代码，已生成的 replace Snapshot、List/Struct Schema 和 Checkpoint 均保持合法 Iceberg 元数据；回滚版本可能无法通过公共 DTO 新增嵌套字段，但已有 Snapshot 仍可由底层 Iceberg 保存。不得通过删除 Snapshot 或降级 Schema 回滚数据。

## Open Questions

无。Cleaner 自动 Checkpoint 命名、Operator ColumnSpec 映射、Importer upsert、Annotation Loader 与 Visualization 的公开 API 留给后续各自 change。
