## Context

DatasetManager 的产品 Backend 由 PostgreSQL/pgvector 控制面、PyIceberg SqlCatalog/Warehouse 和 StorageManager file/S3-compatible IO 组成。仓库虽然提供 `DatasetManager.local()`，但它是 SQLite/JSON 退化的测试 Backend，不适合作为与真实 Backend 等价的用户演示。现有 `sample_1000` 位于 MinIO，并可通过 `notebooks._helpers.datasets` 和旧 Dataset API读取；正式 Importer 尚未切换到 DatasetManager。

本设计面向首次体验与已有环境两类用户：Notebook 应优先复用可用的 `.env`，但连接失败不能静默切换或破坏外部服务；没有服务的用户可以显式创建隔离的 demo 容器。演示材料必须提交到 Git，使 Dataset 生命周期部分在 Backend 准备完成后不再依赖源 MinIO。

## Goals / Non-Goals

**Goals:**

- 提供一个中文、从头可执行的 Notebook，连续演示 DatasetManager 的主要生命周期。
- 自动探测 `.env` 并在连接成功时默认复用已有 PostgreSQL/pgvector、PyIceberg Warehouse 和 MinIO。
- 在配置缺失或连接失败时提供可操作诊断，并允许用户显式创建、重建和清理隔离 demo Backend。
- 从 `sample_1000` 固定抽取并提交 20 张真实图片及来源 manifest。
- 把临时导入适配限制在 examples 内，为后续正式 Importer 替换保留单一切换点。
- 通过自动化验证证明材料完整、危险操作受限、Notebook 无隐藏状态且真实容器路径可运行。

**Non-Goals:**

- 不把 `DatasetManager.local()` 宣传为生产等价 Backend。
- 不修改 DatasetManager、StorageManager 或正式 Importer 公共 API。
- 不自动删除、重建或停止用户在 `.env` 中配置的外部服务。
- 不在 Notebook 内实现向量模型；示例向量保持确定性且明确标注为调用方提供的数据。
- 不把 20 张材料扩展为测试 fixture 或新的正式数据集发行机制。

## Decisions

### 1. 一个 Notebook，后端准备与业务旅程分层

采用 `examples/dataset_manager_demo/dataset_manager_demo.ipynb`。Notebook 前部只负责材料预览、配置探测与 Backend 选择；后部接收统一的 Backend session 后执行同一条 Dataset 旅程。相比两个 Notebook，这避免环境准备之外的代码和说明漂移；相比自动失败回退，显式选择能让用户始终知道数据写入哪里。

### 2. `.env` 自动探测只读且失败即停止

helper 按普通 checkout 与 linked worktree 查找 `.env`，校验必需字段后执行有界连接检查，包括 PostgreSQL、pgvector、Catalog/Warehouse 和 MinIO bucket。全部通过时默认产生 existing session；缺失、不完整或不可连接时返回结构化诊断供 Notebook 展示，后续业务单元格必须拒绝继续。不得因探测失败自动启动容器或改写 `.env`。

备选的“连接失败自动启动容器”被拒绝，因为它会掩盖错误配置并让用户误判数据所在环境。

### 3. 显式命令管理隔离 demo Backend

Notebook 展示 `start_demo_backend(recreate=True)`、`stop_demo_backend(remove_volumes=True)` 等明确命令。实现只识别固定项目名、容器名和 label；重建前必须验证目标均由 demo helper 创建。生成的非敏感连接配置写入 Git 忽略的 `.env.demo`，不覆盖 `.env`。外部 existing session 永不进入容器停止或 volume 删除路径。

容器仍使用 PostgreSQL/pgvector、PyIceberg SqlCatalog 和 MinIO，保证两种环境的领域语义一致。容器资源使用 context/finalizer 兜底，但破坏性清理仍由用户显式触发。

### 4. 固定、可追溯的 20 张材料

实现阶段使用现有 `sample_1000` frame，以固定 seed 无放回抽样 20 行，通过当前 MinIO Dataset 读取 bytes，按稳定本地文件名写入 `materials/raw_images/`。`sample_manifest.json` 记录 seed、总体行数、样本数，以及每项原始 `image_uri`、本地相对路径、SHA-256 和大小。下载只在制备阶段执行；Notebook 运行只使用 Git 内本地文件。

材料验证必须检查恰好 20 个唯一条目、文件存在、非空、可解码且 SHA-256 匹配。manifest 不保存凭证或 endpoint secret。

### 5. examples 内演示 adapter 是唯一临时兼容层

`helpers.py` 接受现有 SourceParser 结果、Dataset target、精确 Branch 基线、StorageManager、Prefix 和 Tag，把本地 bytes 托管写入并构造五个系统字段后一次 commit。它不从 `image_gallery` 导出，也不进入 wheel。Notebook 不从 `tests.helpers` 导入；后续正式 Importer 上线时只替换该 adapter 的调用，不重写生命周期章节。

### 6. 演示旅程覆盖产品语义而非测试内部结构

后半段依次展示 Repo/Dataset/Tag 创建、20 张导入与 V1 commit、行与图片读取、Checkpoint、experiment Branch、main/experiment 独立迭代、固定 View、确定性 VectorField 与 Data+Vector commit、回退、Clone、关闭重连和持久状态。每一阶段包含中文目的说明、少量关键断言和人可读输出；内部故障注入、migration 细节和测试专用诊断不进入主教程。

### 7. 自动化验证分层

快速测试验证 manifest、helper、`.env` 探测状态机、外部环境不可破坏、Notebook 结构和中文说明。带 `dataset_backend` marker 的真实测试启动容器并用无交互执行器从头运行 Notebook；测试提供明确的 demo 操作确认参数并在 finally 中清理。已有外部环境路径通过配置解析与连接 adapter 单元测试覆盖，不要求 CI 持有长期凭证。

## Risks / Trade-offs

- [真实图片增加 Git 体积] → 限制为 20 张，记录总大小并在提交前设置可接受上限，不引入重复或缩略图副本。
- [sample_1000 或 MinIO 暂时不可用导致材料无法制备] → 抽样与下载是一次性实现任务；失败时停止，不提交不完整 manifest，运行时不依赖源服务。
- [Notebook 容器清理误伤用户服务] → 固定 label/项目名双重校验，existing session 与 managed session 使用不同类型，破坏性 API 只接受 managed handle。
- [Notebook 输出和元数据造成噪声] → 提交前清空运行输出，自动测试复制 Notebook 到临时目录执行并检查结果。
- [临时 adapter 被误认为正式 API] → README 和 docstring 明确实验边界，包制品测试断言 examples helper 不进入 wheel。
- [existing 环境权限不足] → 探测阶段分别报告 extension、schema/catalog、warehouse 与 bucket 权限，不在业务单元执行到一半才失败。

## Migration Plan

1. 制备并校验 20 张材料及 manifest。
2. 实现环境探测、managed demo Backend 和临时导入 adapter，并先完成单元测试。
3. 创建 Notebook 与 README，验证 existing 配置指导和 managed 容器路径。
4. 后续正式 Importer 可用时，在新 change 中替换 examples adapter；Notebook 章节和材料保持不变。

回滚只需删除 `examples/dataset_manager_demo/` 及对应测试/文档，不涉及生产数据库迁移或公共 API 回退。

## Open Questions

无。固定抽样 seed、图片总体积上限和具体 demo label 在实现任务中选择并由测试冻结。
