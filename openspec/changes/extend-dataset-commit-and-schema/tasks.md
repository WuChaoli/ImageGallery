## 1. 固化公共契约与回归基线

- [x] 1.1 为 `CommitMode`、默认 `replace`、显式 `upsert`/`patch`、Schema additions、可选 Checkpoint、`CommitResult.removed` 及 `DatasetView` owner 导航补充公共接口契约测试。
- [ ] 1.2 为 `ColumnSpec` 与递归 Schema DTO（primitive、list、struct）补充公共导出、构造、typed introspection、序列化和非法嵌套输入测试，确保公共类型不泄露 PyIceberg field ID。
- [x] 1.3 审计依赖旧 commit 默认语义的调用点，至少覆盖 `tests/helpers/dataset_manager_importer.py`、DatasetManager demo helper/notebook、backend E2E 与单元测试，并明确每处迁移为 `replace`、显式 `upsert` 或显式 `patch`。

## 2. 实现 Dataset commit 模式

- [x] 2.1 先补充 `replace` 的失败测试，覆盖默认调用、空表替换、删除 Head 中缺失行、无变化提交和旧 Snapshot/Checkpoint 仍可读取。
- [x] 2.2 实现默认 `replace`，并保持 `upsert` 与 `patch` 只能通过显式 mode 选择。
- [ ] 2.3 补充外部状态回归测试，证明 `replace` 不删除图片 bytes、Tag Definition、历史 tag 赋值或 Repo 当前向量。
- [x] 2.4 迁移仓库内现有调用点与测试，消除对旧默认 upsert 语义的隐式依赖。
- [x] 2.5 锁定三种模式的 inserted、updated、removed、changed 计算，覆盖未变化重提行、replace 删除和 schema-only change。

## 3. 原子化 commit 与 Checkpoint

- [ ] 3.1 先补充组合发布测试，覆盖显式 Checkpoint 名称、未请求 Checkpoint、名称冲突及中途失败恢复；自动命名留给后续 Cleaner change。
- [x] 3.2 将显式 Schema additions、候选数据、Branch Head 发布和可选 Checkpoint 纳入同一个可恢复 history operation，并让 `CommitResult` 返回最终 View 与可选 Checkpoint 信息。
- [ ] 3.3 为同一 Dataset 的 API operation 与 recovery 增加共享串行化保护；同时需要 Schema lock 时固定先 Repo 后 Dataset 的锁顺序，并覆盖 PostgreSQL advisory lock、同 Backend identity 的两个本地 Manager、两个 recoverer、API/recovery 并发及持锁后状态重查。
- [ ] 3.4 补充各崩溃阶段与中间态可见性测试：active operation 阻断普通 Head/Checkpoint/Schema discovery；data/ref-only 时既有固定 View 可读，含 Schema additions 时其 schema-dependent IO 被阻断；恢复后不永久缺失或重复创建 Checkpoint。
- [ ] 3.5 补充 Schema additions 与数据/Checkpoint 的组合发布测试，覆盖 schema-only、非法 nested value 在 operation 前失败及无隐式 Dataset Checkpoint 自动命名。
- [x] 3.6 覆盖 snapshotless 空 Dataset 的 empty replace：不请求 Checkpoint 时保持无 Snapshot no-op，请求时创建首个空 Snapshot 与 Checkpoint且 changed=False。

## 4. 从固定 DatasetView 创建 Branch

- [ ] 4.1 先补充从 Branch Snapshot 和 Checkpoint 固定视图创建新 Branch 的测试，覆盖来源先推进后仍从 stale-but-valid View 创建，以及创建后来源继续推进不改变新 Branch 起点。
- [ ] 4.2 实现 `create_branch` 接受固定 `DatasetView`，且不为了固定来源而隐式创建 Checkpoint；同时记录 durable intent 与 phase。
- [ ] 4.3 覆盖跨 Repo、跨 Dataset、动态 Head 或无效 Snapshot 来源的拒绝路径。
- [ ] 4.4 增加 Branch ref 创建后失败注入、普通 API reconciling 行为、重启恢复与不重复 ref 的测试。

## 5. 支持递归嵌套 Schema

- [ ] 5.1 实现 `ColumnSpec` 与 primitive/list/struct 递归 DTO，校验有限无环类型树、List element null、Struct 名称/顺序/required，并冻结已创建嵌套结构。
- [ ] 5.2 实现公共 DTO 与 PyArrow/PyIceberg 类型之间的双向转换和 typed Schema discovery；既有 Table ID 稳定，新 Table 递归重分配 ID，系统列、开放列和 schema 演进共用同一入口。
- [ ] 5.3 实现 JSON-safe canonical value 规范化，覆盖 None/空 List、optional/required、pd.NA/NaN、NumPy scalar、bool 与 integer 范围，并补充 SQLite/PostgreSQL journal、Arrow、Iceberg、空表与全空嵌套列 round-trip 测试。
- [ ] 5.4 用 `voc_bbox_to_annotation()` 的真实 Annotation v1 返回值完成 `annotations` 列兼容性测试，覆盖嵌套 bbox、全部现有字段、多标注和空列表。
- [ ] 5.5 补充多层嵌套 field ID 唯一性、Backend 重开稳定性，以及 clone/materialize 到新 Table 后重新分配且无碰撞测试。
- [x] 5.6 将独立 `DatasetSchema.add_column()` 纳入 schema-only durable history operation，复用 Commit 的 pending gate、锁顺序、中间态门禁和 recovery 测试。

## 6. 原子化创建新 Dataset

- [ ] 6.1 先补充 `materialize_dataset` 测试，覆盖从固定 View 创建、来源 View 固定后 Table Schema 演进、目标数据与 Schema、空 frame 空 Snapshot、可选初始 Checkpoint、名称冲突和失败不可见。
- [ ] 6.2 实现 Repo 级 durable materialization operation，使目标 Dataset 仅在 Iceberg table、控制面记录、默认 Branch 和可选 Checkpoint 全部完成后可见。
- [ ] 6.3 在 Catalog 副作用前实现 durable normalized-name reservation，并补充并发同名 winner/loser、中断后同名重试、各阶段恢复和不可见 orphan 测试，确保不误删 winner。
- [ ] 6.4 验证物化过程保留源 `asset_id` 与图片引用，不复制或删除 StorageManager 中的图片 bytes。

## 7. 补齐 View owner 导航与后续适配门禁

- [ ] 7.1 实现 `DatasetView.dataset`/`repo`（或等价 typed owner API），按不可变 ID 在同一 Backend 解析句柄，不复制领域写方法到 View。
- [ ] 7.2 覆盖正常导航、对象尚未 finalize、失效控制面对象和跨 Manager 伪造 View 的失败路径。
- [ ] 7.3 记录后续 change 依赖：Cleaner 自动 Checkpoint 命名与 ColumnSpec 映射、Importer 显式 upsert 与 orphan bytes、Annotation asset_id/bytes IO、Visualization DatasetView/read_image；本 change 不实现这些消费者 API。

## 8. 完成验证与文档收敛准备

- [ ] 8.1 运行 DatasetManager 定向单元测试和契约测试，确认新增失败用例在实现前有效、实现后通过。
- [ ] 8.2 运行 `uv run python -m tools.ci format-check`、`lint`、`docs`、`test` 与 `coverage`。
- [ ] 8.3 运行 `uv run python -m tools.ci dataset-backend`，验证 PostgreSQL、pgvector、PyIceberg 与 S3-compatible Backend 的真实原子性和恢复行为。
- [ ] 8.4 更新 DatasetManager 模块文档与面向人的 README，说明默认 `replace`、历史保留、commit/Checkpoint、固定 View 分支、owner 导航和 typed Schema 契约；最终归档前由 `sync-docs` 收敛。
