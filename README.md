# ImageGallery

ImageGallery 是一个 local-first 的 Python 图片数据集工具包，覆盖图片导入、存储、清洗、查看与导出。

当前版本以 Python package API 和 Jupyter 验证为核心，不包含服务端 API 或 Web UI。

## DatasetManager 新平台

`image_gallery.dataset_manager` 提供与旧 `image_gallery.dataset` 独立并存的新数据集平台：一个 Backend 可创建多个硬隔离的 `DatasetRepo`，每个 Dataset 使用独立 Iceberg Table 管理 Branch、Checkpoint、回退与状态 Clone。`image_gallery.storage_manager` 独立负责 file/S3-compatible Prefix、SHA-256 内容身份和图片 bytes IO。

新平台支持 Repo 级 Tag Definition、Dataset 行内版本化 Tag Assignment，以及由冻结模型生成、pgvector 保存的 Repo 当前 VectorField 值。MVP 不提供 merge、跨 Repo clone、删除/GC、全 Repo embedding 调度、ANN 或语义搜索。

本地开发与单元测试可使用 `DatasetManager.local(...)`；PostgreSQL Backend 通过 `DatasetManager.postgres(...)` 连接 control database 和 PyIceberg SqlCatalog。完整签名和类型以包级导出与 docstring 为准。

Model 与 Storage Prefix 的非敏感冻结定义保存在 PostgreSQL control schema，明文凭证只由部署层的 CredentialProvider 解析。进程重启后相同 `model_id` 和 `prefix_id` 会自动恢复原 provider/backend、artifact/root、endpoint 与 secret reference；模型文件或 Backend 离线不可达时会明确失败，不会静默改绑。`DatasetManager` 会关闭自己创建的 `ModelManager`，但不会关闭调用方注入、可能被共享的实例；外部实例由调用方负责关闭。

Dataset 数据使用 pandas DataFrame 提交和读取。`dataset.commit(...)` 默认以 `replace` 把 frame 发布为目标 Branch 的完整新状态；增量导入必须显式使用 `mode="upsert"`，局部业务列更新使用 `mode="patch"` 和非空 `fields`。Replace 只从新 Head 移除未提交行，既有 Snapshot、Checkpoint、Tag Assignment、图片 bytes 和 Repo 当前向量仍保留。Commit 可以同时发布顶层可选 `ColumnSpec` 和显式命名的 Checkpoint；未传 Checkpoint 名称时不会自动创建。

`dataset.schema` 以 typed `ColumnSpec` 描述标量、List 和 Struct，可承载 Annotation 所需的 `list<struct>`。Branch 可直接从同 Dataset 的任意固定 `DatasetView` 创建，不会为来源隐式打 Checkpoint；View 通过 `dataset` 和 `repo` 属性导航到所属句柄。需要隔离 Schema 或发布筛选结果时，使用 `repo.materialize_dataset(...)` 从同 Repo 固定 View 原子创建独立 Dataset；它复用内容身份与图片位置，不复制 bytes、向量或来源历史。

向量字段不能直接 Commit。先通过 `repo.schema.add_vector(..., model_id=...)` 冻结模型绑定，再调用 `dataset.generate_embed(field=...)` 为 main 当前 Head 的全部行生成，也可指定 Branch 或精确 View。普通列与 VectorField 名称均去除首尾空白后按大小写不敏感规则判重；物理列固定在 Iceberg Snapshot，显式扫描的向量列始终读取 Repo 当前值。

Alembic migration 需要建 schema、extension 和 role 的管理员权限；当前 `DatasetManager` 初始化会自动执行 migration，因此 PostgreSQL 连接默认也需要这些权限。迁移会创建 control、vectors、catalog 三个 runtime role，并把它们授予迁移执行用户。

## 清洗入口

当前 `image_gallery.cleaning` 提供两类面向用户的清洗配置入口：

- `BasicCleaner.from_toml(path)`：从 TOML 配置加载现有清洗规则。
- `BasicCleaner.from_recipe(path)`：从 YAML recipe 加载声明式配方，适合用区间语法表达 `drop` / `review` 阈值。

YAML recipe 当前支持 `version`、`run` 和 `operators` 三段，其中 `operators` 可混用三种写法：

```yaml
version: 1
operators:
  - use: blur
    rules:
      drop: "[0, 0.3]"
      review: "(0.3, 0.6]"
  - use: dimension
    drop:
      min_width: 256
  - use: decode
    action: drop
```

运行时产物存储支持 `DiskRunStore`、`TemporaryRunStore` 和 `MemoryRunStore` 三种实现；默认运行路径仍为磁盘 `cache_root / run_id`，测试或无文件 IO 场景可显式传入其他 `RunStore`。

## 文档

- 当前产品行为：`openspec/specs/`
- 活动设计与实现状态：`openspec/changes/`
- AI 开发规范：根目录及各模块的 `AGENTS.md`

`docs/superpowers/` 只保留历史设计记录，不是当前开发的权威来源。

## 测试分层

默认测试使用仓库内固定的 `tests/fixtures/sample_10/` 本地样本，不依赖 MinIO。可直接运行：

```bash
uv run python -m tools.ci test
```

依赖 `sample_1000` 和 MinIO 的真实数据验收已隔离到 `real_dataset` 层，需要显式运行：

```bash
uv run python -m tools.ci test-real
```

DatasetManager 的 PostgreSQL、pgvector、PyIceberg 和 S3-compatible 容器验收使用独立 `dataset_backend` marker，默认快测不会启动容器：

```bash
uv run python -m tools.ci dataset-backend
```

## CI 安全门槛

面向 `master` 的 Pull Request 会运行以下硬门禁：

- `CI / lint`、`CI / test`、`CI / coverage`、`CI / package`：检查格式、精选 Ruff 安全/风格规则、Pyright、文档与 OpenSpec、默认测试、90% 全仓覆盖率、80% 变更覆盖率、公开接口契约，以及 wheel/sdist 的内容、重建和隔离安装。
- `CI / compatibility-python-3.14`：在实施时确认的最新稳定 Python 上运行快速测试与包安装；最低支持版本 Python 3.10 由其他 CI job 显式安装。
- `Security / secrets`、`Security / dependencies`、`Security / workflows`：检查提交中的密钥、Python 已知依赖漏洞和 GitHub Actions 自身的权限及注入风险。
- `CodeQL`：对 Python 与 GitHub Actions 执行跨文件数据流分析；平台侧只应将新增 High/Critical 告警配置为合并阻断。

本地可使用以下等价入口复现失败：

```bash
uv run python -m tools.ci format-check
uv run python -m tools.ci lint
uv run python -m tools.ci docs
uv run python -m tools.ci test
uv run python -m tools.ci coverage
uv run python -m tools.ci security
uv run python -m tools.ci package
uv run python -m tools.ci package-validate
uv run python -m tools.ci package-smoke
uv run python -m tools.ci sbom
```

这些命令在 Windows、Linux 和 GitHub Actions 中使用相同参数，`tools.ci` 是唯一权威命令入口。

任何已知依赖漏洞都会阻断合并。安全告警不得通过禁用整个扫描器或跳过源码目录来处理。`noqa`、`type: ignore` 与 `pyright: ignore` 必须限定具体规则；批处理、插件、IO adapter 和调度隔离边界的 `BLE001` 还必须逐行写明理由。确属误报或暂不可修复时，在 `.security-exceptions.yml` 中登记具体发现；每条例外必须包含 `id`、`tool`、`scope`、`reason`、`owner` 和 `expires`，过期例外会让 CI 失败。真实密钥一旦进入 Git 历史，必须立即吊销和轮换，仅删除文件或添加豁免不能消除泄露。

每周定时任务会重新扫描主分支和完整 Git 历史。`Deep quality reports` 另行运行可复现随机顺序、`stability` 五次重复、Vulture、第三方 warning、外部链接、全支持 Python 版本和核心纯逻辑 mutation 报告；这些检查不属于普通 PR required checks，也不会自动删除代码。手动触发 `Release artifacts` 时，只有 LICENSE 及包元数据已由用户明确确认，且 wheel/sdist 验证、从目标 wheel 隔离环境生成的 SBOM 和 artifact attestation 全部成功，构建产物才会上传；仓库当前尚未选择许可证，因此正式发布会明确失败。SBOM 和来源证明只提供组件清单与构建来源，不代表代码不存在漏洞。force push、删除分支和管理员日常绕过均被禁止；紧急恢复只能由管理员临时修改保护规则，并保留 GitHub 审计记录。
