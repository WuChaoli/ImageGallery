# ImageGallery

ImageGallery 是一个 local-first 的 Python 图片数据集工具包，覆盖图片导入、存储、清洗、查看与导出。

当前版本以 Python package API 和 Jupyter 验证为核心，不包含服务端 API 或 Web UI。

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

Makefile 当前作为兼容别名保留，已安装 GNU Make 时仍可运行 `make test`。

依赖 `sample_1000` 和 MinIO 的真实数据验收已隔离到 `real_dataset` 层，需要显式运行：

```bash
uv run python -m tools.ci test-real
```

## CI 安全门槛

面向 `master` 的 Pull Request 会运行以下硬门禁：

- `CI / lint`、`CI / test`、`CI / coverage`、`CI / package`：检查格式、精选 Ruff 安全/风格规则、Pyright、文档与 OpenSpec、默认测试、89% 全仓覆盖率、80% 变更覆盖率，以及 wheel/sdist 的内容、重建和隔离安装。
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

这些命令在 Windows、Linux 和 GitHub Actions 中使用相同参数。Makefile 当前仅提供兼容别名，权威实现位于 `tools.ci`。

任何已知依赖漏洞都会阻断合并。安全告警不得通过禁用整个扫描器或跳过源码目录来处理。`noqa`、`type: ignore` 与 `pyright: ignore` 必须限定具体规则；批处理、插件、IO adapter 和调度隔离边界的 `BLE001` 还必须逐行写明理由。确属误报或暂不可修复时，在 `.security-exceptions.yml` 中登记具体发现；每条例外必须包含 `id`、`tool`、`scope`、`reason`、`owner` 和 `expires`，过期例外会让 CI 失败。真实密钥一旦进入 Git 历史，必须立即吊销和轮换，仅删除文件或添加豁免不能消除泄露。

每周定时任务会重新扫描主分支和完整 Git 历史。`Deep quality reports` 另行运行可复现随机顺序、`stability` 五次重复、Vulture、第三方 warning、外部链接、全支持 Python 版本和核心纯逻辑 mutation 报告；这些检查不属于普通 PR required checks，也不会自动删除代码。手动触发 `Release artifacts` 时，只有 LICENSE 及包元数据已由用户明确确认，且 wheel/sdist 验证、从目标 wheel 隔离环境生成的 SBOM 和 artifact attestation 全部成功，构建产物才会上传；仓库当前尚未选择许可证，因此正式发布会明确失败。SBOM 和来源证明只提供组件清单与构建来源，不代表代码不存在漏洞。force push、删除分支和管理员日常绕过均被禁止；紧急恢复只能由管理员临时修改保护规则，并保留 GitHub 审计记录。
