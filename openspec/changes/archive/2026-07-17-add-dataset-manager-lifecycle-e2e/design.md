## Context

现有 DatasetManager 测试分成两层：local backend 单元测试覆盖历史、并发和恢复细节，真实 backend E2E 覆盖 PostgreSQL、pgvector、PyIceberg 与 MinIO 的部分串联。当前真实 E2E 直接写入测试 bytes 并手工构造行，只执行一次有效 commit；它没有证明真实来源解析、多轮历史、分支分叉、rollback 和进程级重开能够形成完整生命周期。此外，Windows 上的真实 E2E 曾在容器健康后长时间不退出，需要把资源关闭和阶段诊断纳入测试设计。

正式 `image_gallery.importers.ImportPipeline` 仍依赖旧 Dataset/Storage 契约。本 change 不提前迁移该产品接口，而是在测试目录建立最小 importer seam，以验证新平台并为未来正式迁移提供可替换的测试入口。

## Goals / Non-Goals

**Goals:**

- 从真实图片目录和现有 `SourceParser` 开始验证 DatasetManager 完整用户旅程。
- 使用真实 PostgreSQL/pgvector、PyIceberg Warehouse、file 与 MinIO StorageManager。
- 在一个可读的 E2E 中验证导入、读取、多轮 commit、固定 View、Checkpoint、Branch 分叉、rollback、Clone、Tag、Vector、冲突和重启重开。
- 使测试专用 importer 的边界足够小，未来可由正式 Importer 替换而不重写生命周期断言。
- 补齐 Vector 验证集和组合提交并发矩阵的明确缺口。
- 保证测试成功或失败后关闭 Manager、Catalog、SQLAlchemy engine、fsspec/S3 client 和 testcontainers。

**Non-Goals:**

- 不修改或兼容现有正式 `ImportPipeline`，不在 `src/` 增加新 Importer API。
- 不实现 URL 下载、失败清单、重试、断点续传、批量分片、元数据抽取或导入任务状态。
- 不使用 `sample_1000`，不把真实后端测试并入默认快速测试。
- 不改变 DatasetManager、StorageManager、Tag、Vector 或历史的产品语义。

## Decisions

### 1. 测试专用 Importer 放在 tests/helpers

新增私有测试类，例如 `DatasetManagerTestImporter`，位于 `tests/helpers/dataset_manager_importer.py`。它接收 `SourceParser`、目标 Dataset、Branch 基线 View、StorageManager 和 Prefix ID，返回包含提交后 View、导入数量和 asset IDs 的冻结结果 DTO。

相比在 E2E 内写一个局部 fixture 函数，独立测试 helper 能清晰表达未来正式 Importer 的替换缝；相比现在定义生产 Protocol，它不会过早冻结尚未设计的公共 API。

### 2. Importer 只负责最小转换和一次原子提交

Importer 逐项读取 `SourceRecord.local_path`，调用 `StorageManager.write_managed()` 获得规范 SHA-256 identity 与正式位置，然后构造五个系统字段并执行一次 `Dataset.commit()`。`source_uri` 保留追溯信息，`tag_ids` 由调用方提供已存在的 Repo Tag ID。

测试 importer 不抽取旧 RawDatasetSchema 元数据，也不模拟旧 ImportPipeline 的逐项失败语义。来源缺失、非本地 record、Storage 或 commit 错误直接使测试失败，避免测试帮助层吞掉真实问题。

### 3. E2E 使用小型隔离图片集而非外部样本

测试在临时目录生成或复制少量合法图片，使用 `LocalPathParser` 递归发现。图片内容、路径和预期 SHA-256 均确定，不依赖网络、用户 MinIO 或 `sample_1000`。真实 backend 仍由 testcontainers 提供 PostgreSQL/pgvector 与 MinIO。

### 4. 生命周期按可观察状态分阶段断言

E2E 明确形成 V1、V2、V3：V1 导入并建立 Checkpoint；从 V1 创建 experiment；main 和 experiment 分别提交不同变化；确认 V1 View 与 Checkpoint 不漂移；main 回退到祖先 Checkpoint，同时 experiment 保持分叉状态。随后关闭全部客户端，创建新 Manager/StorageManager，使用稳定 Prefix ID 重建配置并重新打开 Repo、Dataset、Refs、Clone、Tag 和 Vector。

每个阶段断言业务可观察状态，不读取任意内部 snapshot，不依赖 Iceberg 实现细节。stale-base 冲突和 Data+Vector commit 也在真实 backend 上至少各验证一次。

### 5. 资源生命周期必须由嵌套 context manager 管理

测试对 StorageManager 和 DatasetManager 使用 context manager；fixtures 继续用容器 context manager。若某第三方客户端仅提供异步关闭路径，生产对象的 `close()` 必须统一等待完成。E2E 使用阶段标记或 pytest 日志区分 fixture setup、test body 和 teardown，超时诊断必须能指出阻塞阶段。

相比单纯提高测试超时，这能暴露连接泄漏；相比在测试结束时强杀容器，它保留真实资源生命周期验证。

### 6. Vector 边界测试保持单元级

验证输出乱序、容差内/外、Inf，以及组合 commit 的 stale Branch View 属于确定性领域边界，放在 unit tests；完整 E2E 只保留一个成功 Data+Vector commit 和可读取断言，避免真实容器测试膨胀成故障矩阵。

## Risks / Trade-offs

- [测试 helper 与未来正式 Importer 形状不同] → 只共享 `SourceParser` 输入和可观察 Dataset 结果，不建立生产继承或 Protocol；正式迁移时替换 helper 调用点。
- [一次原子 commit 无法表达正式导入的部分失败策略] → 本 change 明确只验证成功旅程，失败清单和重试由正式 Importer change 设计。
- [Windows 容器冷启动较慢] → 保留 `dataset_backend` marker，设置基于实际冷启动的测试超时，并输出阶段诊断，而不是加入默认测试。
- [重启时 Prefix registry 本身不持久化] → 使用显式稳定 `prefix_id` 重新注册相同配置，验证 Dataset 行中的引用在客户端重建后仍可解析。
- [单一长 E2E 定位失败较慢] → migration smoke 独立保留；完整旅程按阶段组织断言和日志，同时避免拆成无法证明端到端协作的多个假 E2E。

## Migration Plan

1. 先为测试 importer 写 local backend 单元测试，冻结转换、稳定 asset ID、Tag 与原子 commit 行为。
2. 增加真实后端生命周期 E2E，并修复由它揭示的资源生命周期问题。
3. 补齐 Vector 单元测试矩阵并运行 scoped、默认、coverage 和真实 backend 验证。
4. 未来正式 Importer 接入 DatasetManager 后，将 E2E 的 importer fixture 替换为正式类；删除测试 helper，不改变生命周期断言。

本 change 仅增加测试代码和必要的资源生命周期修复，回滚时可移除 helper 与新增测试，不涉及数据迁移。

## Open Questions

无阻塞问题。正式 Importer 的公共签名、批量策略和失败模型明确延后。
