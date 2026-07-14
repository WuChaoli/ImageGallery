## Context

当前 Makefile（23 行）使用 "OS 判断 + wildcard 检测 venv 路径" 的模式调用 Python，这种方式：
- 跨平台脆弱（需要维护两套 venv 路径）
- 与项目已有的 `uv` 工具链重复
- 缺少现代 Makefile 应具备的开发效率设施（并行测试、格式化、增量检查等）

LangChain 的 Makefile 提供了可参考的最佳实践：直接依赖 `uv run` 管理环境，并通过 `--disable-socket`、`-n auto` 等 pytest 选项增强测试可靠性。

## Goals / Non-Goals

**Goals:**
- 将 Makefile 从 23 行扩展到约 50-60 行，覆盖 7 项优化
- 全部使用 `uv run` 替代手动 venv 路径检测
- 测试添加并行执行和网络隔离
- 新增格式化、增量 lint、help 等 target
- 保持向后兼容：现有 `make lint` / `make test` / `make check` 行为不变

**Non-Goals:**
- 不修改 `pyproject.toml` 中的任何配置
- 不添加 CI/CD 流水线配置（仅为本地开发工具入口）
- 不引入新的外部依赖（pytest-xdist 已在 dev 依赖中）

## Decisions

### 决策 1：用 `uv run` 替代 venv 路径检测

**方案**：删除 OS 检测和 `wildcard` 回退逻辑，所有 Python 命令改用 `uv run --group <group>`。

**理由**：
- 项目已统一使用 `uv` 管理环境，`uv run` 会自动定位 `.venv`
- 消除 14 行跨平台适配代码
- 与 LangChain 做法一致，已被大规模项目验证

**注意**：`uv sync` 后 `.venv` 即就绪，`uv run` 无需额外配置。

### 决策 2：测试网络隔离 + 并行

**方案**：`make test` 添加 `-n auto` 和 `--disable-socket --allow-unix-socket`。

**理由**：
- `-n auto` 按 CPU 核数并行执行，加速测试套件
- `--disable-socket` 拦截单元测试中的意外网络请求（如误连 MinIO）
- `--allow-unix-socket` 允许 Unix socket（pytest-xdist 需要）

### 决策 3：分层 lint

**方案**：保留 `lint` 为全量检查，新增 `lint_package`（仅 `src/`）和 `lint_tests`（仅 `tests/`），通过 `PYTHON_FILES` 变量统一逻辑。

**理由**：
- CI 中修改包代码时只需 `lint_package`，无需扫描测试文件
- 同一份 recipe 通过变量切换 scope，避免 recipe 重复

### 决策 4：`lint_diff` 的实现方式

**方案**：`lint_diff` 使用 `git diff --name-only --diff-filter=d master` 获取变更文件列表，仅对这些文件执行 ruff + pyright。

**理由**：
- 在 PR 中提供秒级反馈，不必等全量检查
- LangChain 已验证此模式有效

## Risks / Trade-offs

- **[git diff 依赖 master]** `lint_diff` 需要 `master` 分支存在且已 fetch → **Mitigation**: 如果 `master` 不存在或 diff 为空，`lint_diff` 优雅降级为空操作
- **[`uv run` 小开销]** 每次 target 执行都启动 `uv run` 进程，有约 100ms 开销 → **Mitigation**: 对于开发场景可忽略，如有需要可在 Makefile 中缓存变量
- **[pytest-xdist 兼容性]** 某些测试可能不兼容并行执行 → **Mitigation**: `-n auto` 默认开启；如遇不兼容测试，可用 `-n 0`（单进程）或 `PYTEST_EXTRA` 覆盖
