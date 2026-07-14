## Why

当前 Makefile（23 行）功能单一，仅包装了 lint/test/check 三个命令。与 LangChain 等成熟项目的 Makefile 相比，缺少测试网络隔离、并行执行、格式化、增量检查等开发效率和可靠性保障设施。趁项目早期修正成本低，将 Makefile 升级为一份高效的开发工具入口。

## What Changes

1. **移除 venv 路径检测**：改用 `uv run` 替代手动检测 `.venv/Scripts/python.exe` vs `.venv/bin/python`，消除跨平台兼容代码
2. **测试并行与网络隔离**：`make test` 添加 `-n auto`（pytest-xdist 并行）和 `--disable-socket --allow-unix-socket`（网络隔离，防止单元测试意外依赖外部服务）
3. **新增 `lint_diff` target**：仅对当前分支相比 master 的变更文件执行 lint，用于 CI 快速反馈
4. **新增 `format` target**：一键 ruff 格式化代码 + 修复 lint
5. **新增 `help` target**：自文档化，输出所有可用命令及用途说明
6. **`TEST_FILE` 变量化**：支持 `make test TEST_FILE=tests/unit/foo.py` 灵活指定测试文件
7. **分层 lint target**：新增 `lint_package`（仅 `src/`）和 `lint_tests`（仅 `tests/`），精细控制 lint 范围

## Capabilities

### New Capabilities

无。本次变更仅修改开发工具链入口，不涉及功能规格行为变更。

### Modified Capabilities

无。

## Impact

- **修改文件**：`Makefile`（根目录）
- **无代码影响**：不修改 `src/`、`tests/`、`pyproject.toml` 或任何依赖
