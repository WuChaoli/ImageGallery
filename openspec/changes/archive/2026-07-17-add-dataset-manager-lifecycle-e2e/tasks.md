## 1. 测试专用 Importer 契约

- [x] 1.1 先编写测试专用 Importer 的失败测试，冻结 `SourceParser`、目标 Dataset、Branch 基线 View、StorageManager、Prefix ID 和 Tag IDs 输入，以及固定结果 DTO。
- [x] 1.2 在 `tests/helpers/dataset_manager_importer.py` 实现最小 `DatasetManagerTestImporter`，逐项读取 local_path、调用 `write_managed`、构造五个系统字段并执行一次原子 commit。
- [x] 1.3 增加真实图片目录测试，证明 `LocalPathParser` 解析结果可导入、SHA-256 asset_id 稳定、source_uri 保留、Tag IDs 规范化且所有图片可读回。
- [x] 1.4 增加无 local_path、Storage 写入失败和 stale Branch View 测试，证明测试 helper 不吞异常且不把部分 Dataset 状态报告为成功。
- [x] 1.5 增加制品边界测试，断言测试 Importer 不从 `image_gallery` 导出且不包含在 wheel 中。

## 2. Vector 验证与组合提交矩阵

- [x] 2.1 先补 VectorField 多 probe 验证集测试，覆盖数量正确但顺序错误，并断言失败后现有向量不变。
- [x] 2.2 补比较容差边界测试，分别证明容差内输出通过、刚超过容差的输出整批失败。
- [x] 2.3 补 NaN、正 Inf、负 Inf 测试，同时覆盖验证输出和目标向量，断言任何非有限值均不发布。
- [x] 2.4 补 Data+Vector 组合提交 stale Branch View 测试，断言 Dataset Head、pending vectors 与 current vectors 均不改变。
- [x] 2.5 若新增测试暴露实现缺口，以最小修改修复验证或 preflight 顺序，并保持现有 Vector API 不变。

## 3. 真实后端资源生命周期

- [x] 3.1 为当前真实 E2E 增加 setup、body、teardown 阶段诊断与合理超时，复现并定位 Windows 上测试超过六分钟不退出的具体边界。
- [x] 3.2 为 DatasetManager、PyIceberg Catalog、SQLAlchemy engine、StorageManager 和 fsspec/S3 client 增加或强化 close/context-manager 测试，先证明泄漏或阻塞路径。
- [x] 3.3 仅在根因证据要求时修复资源关闭实现，确保同步 `close()` 等待必要的异步 session 关闭且可以幂等调用。
- [x] 3.4 分别运行 migration 与最小真实 E2E，证明成功和故障路径均在配置超时内退出且不残留 testcontainers 或 pytest 子进程。

## 4. 完整 Dataset 生命周期 E2E

- [x] 4.1 建立包含少量确定性合法图片的隔离来源 fixture，并准备可用稳定 ID 重建的 file 与 MinIO Prefix 配置。
- [x] 4.2 使用测试 Importer 在真实 Backend 导入 V1，验证 Repo/Dataset 注册、托管 bytes、SHA-256 行身份、Tag、Data+Vector 原子 commit 和按 asset_id 读取。
- [x] 4.3 在真实 Backend 创建 V1 Checkpoint 与 experiment Branch，分别推进 main 和 experiment，形成明确 V2/V3 分叉并验证旧 View 与 Checkpoint 不漂移。
- [x] 4.4 验证 stale-base 冲突、main 回退到祖先 Checkpoint、experiment 保持独立，以及从固定 View Clone 后图片与 Repo 当前向量复用但历史独立。
- [x] 4.5 显式关闭第一组 Manager/Storage 客户端，以相同 PostgreSQL/Catalog/Warehouse 配置和稳定 Prefix ID 重建客户端，重新打开并验证 Repo、Dataset、Refs、Clone、图片、Tag 与 Vector 持久状态。
- [x] 4.6 保留独立 migration smoke，并把完整旅程标记为 `dataset_backend`，确保默认快速测试不启动网络或容器。

## 5. 验证与交付

- [x] 5.1 运行测试 Importer、Vector、资源生命周期相关单元测试，确认新增用例会在对应行为被破坏时失败。
- [x] 5.2 分别运行 PostgreSQL migration 和完整生命周期真实 E2E，记录执行时间并确认进程、容器和客户端正常收尾。
- [x] 5.3 运行新模块 scoped coverage，确保 DatasetManager/StorageManager 核心模块行覆盖率不低于 90%，并检查新增关键分支均有直接证据。
- [x] 5.4 按仓库 PR 前顺序运行 format-check、lint、docs、test、coverage、security、package、package-validate 和 package-smoke，所有命令退出码为 0。
- [x] 5.5 运行 `openspec validate add-dataset-manager-lifecycle-e2e --strict` 与 `git diff --check`，复核测试 helper 未进入生产包且没有修改正式 Importer API。
