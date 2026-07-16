## Why

仓库当前以 Makefile 聚合开发与 CI 命令，但 Windows 开发环境默认不提供 GNU Make，导致本地验证与 GitHub Actions 使用不同入口。同时仓库虽已提供 `ruff format` 修改命令，却没有将格式检查定义为可阻断 PR 的正式规范。

## What Changes

- 新增基于 Python 的跨平台 CI 命令入口，统一调度格式化、lint、测试、安全检查和包验证。
- 将 Makefile 收敛为调用 Python CI 入口的薄兼容层，本轮不删除现有 Make 目标。
- 区分会修改文件的 `format` 与只检查的 `format-check`，并由 Ruff 统一负责 Python 格式化和 import/lint 修复。
- 在 Pull Request 的 required lint check 中执行 `ruff format --check`，格式不合规时阻止合并。
- 保持默认快速测试与显式真实数据测试分层，不引入 Black、isort、Nox 或 Tox。
- 将删除 Makefile 明确留到后续独立变更，前提是 Windows 手动验证与 GitHub CI 均确认 Python 入口可用。

## Capabilities

### New Capabilities

- `developer-command-harness`: 定义跨平台 Python CI 入口、任务集合、失败传播与 Makefile 兼容边界。

### Modified Capabilities

- `lint-pipeline`: 增加 Ruff 格式检查契约，并将统一 lint 入口从 Makefile 迁移到 Python CI 入口。
- `ci-security-gates`: 要求 GitHub CI 调用跨平台 Python 入口，同时保持稳定的 required check 名称。

## Impact

- 新增仓库级 Python CI 调度模块及相应单元测试。
- 修改 `Makefile`、`.github/workflows/*.yml`、`pyproject.toml` 中的工具配置，以及开发者命令文档。
- 不修改 `src/image_gallery/` 的公共 API、数据契约或运行时行为，不新增第三方格式化或任务运行依赖。
