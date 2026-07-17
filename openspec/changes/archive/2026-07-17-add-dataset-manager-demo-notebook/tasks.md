## 1. 演示材料制备

- [x] 1.1 先为 manifest 校验器编写失败测试，冻结固定 seed、总体行数、20 个唯一条目、必需字段、文件存在性、可解码性与 SHA-256 契约。
- [x] 1.2 实现一次性材料制备入口，从现有 `sample_1000` frame 固定无放回抽样 20 行，并通过当前 MinIO Dataset API 下载原始 bytes。
- [x] 1.3 将图片写入 `examples/dataset_manager_demo/materials/raw_images/`，生成不含凭证的 `sample_manifest.json`，并运行校验器证明内容完整可追溯。
- [x] 1.4 复核 20 张图片的总 Git 体积、扩展名和重复 hash，确保没有异常大文件、空文件或重复材料。

## 2. 环境配置与自动探测

- [x] 2.1 为 `.env` 候选路径、字段缺失、连接成功和各服务失败状态编写单元测试，冻结结构化诊断 DTO。
- [x] 2.2 在 examples helper 实现只读 `.env` 探测、敏感值遮蔽和有界 PostgreSQL/pgvector、Catalog/Warehouse、MinIO 检查。
- [x] 2.3 增加 `.env.example` 与中文 README 配置表，确保示例覆盖已有环境所需字段但不包含真实凭证。
- [x] 2.4 增加门禁，证明配置缺失或连接失败时不会创建容器、覆盖 `.env` 或允许 Dataset 业务旅程继续。

## 3. 隔离 demo Backend 管理

- [x] 3.1 先为 managed/existing session 类型、固定 demo label、recreate 目标校验和 external session 拒绝破坏性清理编写测试。
- [x] 3.2 实现 `start_demo_backend(recreate=False/True)`，使用 PostgreSQL/pgvector 与 MinIO 容器建立 PyIceberg SqlCatalog/Warehouse，并返回统一 Backend session。
- [x] 3.3 生成 Git 忽略的 `.env.demo`，证明不覆盖 `.env`，且日志、Notebook 输出和异常均不泄露数据库或 MinIO 凭证。
- [x] 3.4 实现 `stop_demo_backend(remove_volumes=...)` 和进程退出兜底，只操作 label 与项目名同时匹配的 managed 容器和 volume。
- [x] 3.5 增加 Docker 不可用、端口分配失败、启动超时和中途异常测试，证明失败路径会释放已创建资源并给出中文修复信息。

## 4. 演示导入与共享 helper

- [x] 4.1 为 examples 内演示 adapter 编写测试，覆盖 SourceParser 输入、精确 Branch 基线、Tag 规范化、20 张批量原子 commit 和图片读回。
- [x] 4.2 实现 examples 范围的临时 DatasetManager 导入 adapter，复用 StorageManager 托管写入并构造五个系统字段，不从 `tests.helpers` 或生产包导入临时对象。
- [x] 4.3 增加 local material 缺失、Storage 失败和 stale base 测试，证明失败不会发布部分 Dataset commit。
- [x] 4.4 增加 wheel/公共导出边界测试，证明 examples adapter 不进入制品且正式 `image_gallery.importers` API 无变化。

## 5. 中文 DatasetManager Notebook

- [x] 5.1 创建 `dataset_manager_demo.ipynb` 的中文教学骨架，分离材料预览、环境探测、显式创建/重建 Backend、生命周期旅程和清理章节。
- [x] 5.2 实现已有 `.env` 成功时的默认连接流程，以及缺失/失败时的中文告警、`.env.example` 指导和显式 `start_demo_backend(recreate=True)` 示例。
- [x] 5.3 演示 Repo、Dataset、Storage Prefix、Tag 创建，导入 20 张图片并一次提交 V1，展示行、Tag、图片读取和内容身份。
- [x] 5.4 演示 V1 Checkpoint、experiment Branch、main 与 experiment 独立 version commit，并展示固定 View 与分支状态差异。
- [x] 5.5 演示确定性 VectorField、Data+Vector commit 与 Repo 当前向量语义，明确说明示例不包含向量模型生成。
- [x] 5.6 演示 main 回退、从固定 View Clone、关闭 Manager/Storage 后重新连接，并验证 Repo、Dataset、Refs、Clone、图片、Tag 与 Vector 持久状态。
- [x] 5.7 增加 existing 环境演示数据清理和 managed 容器清理章节，所有破坏性命令均需用户显式执行并说明影响范围。
- [x] 5.8 清空提交版 Notebook 输出与运行时标识，证明 Restart Kernel 后按顺序执行不依赖隐藏变量或手工跳步。

## 6. 文档、自动化验证与交付

- [x] 6.1 更新 `examples/README.md` 和演示目录 README，说明适用环境、快速开始、`.env` 配置、显式重建、安全边界和临时 importer 限制。
- [x] 6.2 增加 Notebook 静态测试，检查章节顺序、中文说明、无硬编码凭证、无 SQLite 等价 Backend 表述和无 `tests.helpers` 依赖。
- [x] 6.3 增加带 `dataset_backend` marker 的隔离 Notebook 执行测试，从干净 kernel 跑完 managed 路径并在 finally 中确认无残留 demo 容器或客户端进程。
- [x] 6.4 运行材料、环境、Backend manager、adapter 和 Notebook 相关快速测试及 scoped coverage，确保关键状态机和危险分支有直接证据。
- [x] 6.5 运行真实 Notebook E2E，记录执行时间，检查持久重连、资源关闭、输出脱敏和 Git 工作树无运行时产物。
- [x] 6.6 按仓库 PR 前顺序运行 format-check、lint、docs、test、coverage、security、package、package-validate 和 package-smoke，所有命令退出码为 0。
- [x] 6.7 运行 `openspec validate add-dataset-manager-demo-notebook --strict` 与 `git diff --check`，复核生产 API 未变化、图片 manifest 完整且 `.env.demo`/runtime 未进入 Git。
