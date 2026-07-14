# ImageGallery

ImageGallery 是一个 local-first 的 Python 图片数据集工具包，覆盖图片导入、存储、清洗、查看与导出。

当前版本以 Python package API 和 Jupyter 验证为核心，不包含服务端 API 或 Web UI。

## 文档

- 当前产品行为：`openspec/specs/`
- 活动设计与实现状态：`openspec/changes/`
- AI 开发规范：根目录及各模块的 `AGENTS.md`

`docs/superpowers/` 只保留历史设计记录，不是当前开发的权威来源。

## CI 安全门槛

面向 `master` 的 Pull Request 会运行两组 required checks：

- `CI / lint`、`CI / test`、`CI / package`：检查代码风格、类型、行为测试以及 wheel 的构建和隔离安装。
- `Security / secrets`、`Security / dependencies`、`Security / workflows`：检查提交中的密钥、Python 已知依赖漏洞和 GitHub Actions 自身的权限及注入风险。

本地可使用以下等价入口复现失败：

```bash
make lint
make test
make security
make package package_smoke sbom
```

Windows 未安装 GNU Make 时，分别运行：

```powershell
uv run ruff check src tests
uv run pyright src/image_gallery
uv run pytest -n auto --disable-socket --allow-unix-socket tests/
uv run python tools/check_security_exceptions.py
gitleaks git --redact --no-banner .
uv run pip-audit --progress-spinner off
uv run zizmor .github/workflows
uv run python -m build --outdir .tmp/ci-dist
```

任何已知依赖漏洞都会阻断合并。安全告警不得通过禁用整个扫描器或跳过源码目录来处理。确属误报或暂不可修复时，在 `.security-exceptions.yml` 中登记具体发现；每条例外必须包含 `id`、`tool`、`scope`、`reason`、`owner` 和 `expires`，过期例外会让 CI 失败。真实密钥一旦进入 Git 历史，必须立即吊销和轮换，仅删除文件或添加豁免不能消除泄露。

每周定时任务会重新扫描主分支和完整 Git 历史。手动触发 `Release artifacts` 工作流后，只有 wheel 隔离安装、SBOM 和 artifact attestation 全部成功，构建产物才会上传。当前仓库为私有仓库，CodeQL 与 GitHub Secret Scanning 仍需在仓库套餐支持并启用后加入 required checks。
