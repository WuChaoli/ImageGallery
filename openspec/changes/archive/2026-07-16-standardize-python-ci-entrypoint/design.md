## Context

仓库当前通过 Makefile 聚合 Ruff、Pyright、pytest、安全检查和包构建。GitHub Actions 可以安装 Make，但 Windows 开发环境通常不能直接运行同一入口，实际验证只能退回到底层 `uv run` 命令。与此同时，Makefile 已有 `format` 目标，却没有只读格式检查，CI 因此无法阻止未格式化代码进入默认分支。

本变更跨越本地开发命令、GitHub Actions 和 lint 契约，但不改变产品运行时。设计需要保证入口跨平台、失败码透明、底层命令易排障，并为 Makefile 提供明确的兼容退出路径。

## Goals / Non-Goals

**Goals:**

- 用仅依赖 Python 与 uv 的入口统一 Windows、Linux 和 GitHub Actions 行为。
- 将格式修改与格式检查拆分，并把格式检查设为 PR 硬门槛。
- 保留现有任务语义和 fast default / slow explicit real-data 测试分层。
- 在兼容期让现有 Make 目标转发到同一个 Python 实现。

**Non-Goals:**

- 本轮不删除 Makefile，也不承诺删除日期。
- 不引入 Black、isort、Nox、Tox 或通用 CLI 框架。
- 不改变 `src/image_gallery/` 公共 API、测试数据策略或安全风险阈值。
- 不在本轮扩大 Ruff lint 规则集；格式化迁移与规则扩展分开评审。

## Decisions

### 1. 使用轻量 Python 模块作为权威命令入口

入口采用 `uv run python -m tools.ci <task>`，任务名称保持显式且有限：`format`、`format-check`、`lint`、`test`、`test-real`、`test-all`、`check`、`security`、`package` 和必要的底层安全任务。模块只负责声明固定 argv、顺序执行和传播非零退出码，不实现 shell、插件发现、配置继承或任意命令执行。

相比继续以 Makefile 为权威入口，该方案不要求 Windows 安装 GNU Make；相比引入 Nox/Tox，它复用现有 uv 环境且不增加依赖；相比把所有命令写入 `pyproject.toml`，Python 模块更适合表达组合任务并可直接单元测试。

### 2. subprocess 使用固定参数并立即失败

调度器使用参数列表调用子进程，不启用 `shell=True`。组合任务按确定顺序执行，首个失败立即返回其非零退出码。输出直接继承当前终端，避免包装层隐藏 Ruff、Pyright 或 pytest 的原始诊断。

任务实现与产品包隔离，放在仓库级 `tools` 模块，不纳入发布 wheel。测试通过替换进程执行边界验证命令、顺序和失败传播，不真正递归运行全套 CI。

### 3. Ruff 是唯一 Python formatter

`format` 依次执行 `ruff check --fix` 与 `ruff format`，用于开发者主动修改代码；`format-check` 只执行 `ruff format --check`。`lint` 保持 `ruff check` 与 Pyright 的检查职责，不自动修改文件。

`check` 组合 `format-check`、`lint` 和默认快速测试。格式范围至少覆盖 `src`、`tests` 和本轮新增的 `tools`，所有入口从同一个任务定义获取范围，防止本地和 CI 漂移。现阶段不叠加 Black 或 isort，避免多个工具争夺格式所有权。

### 4. Makefile 仅保留薄兼容转发

现有目标名称在兼容期保留，但目标体只调用对应 Python 任务，不再复制 Ruff、Pyright、pytest 等底层参数。新增 `format_check` 转发目标。帮助文本明确 Python 入口是权威入口、Makefile 是兼容别名。

删除 Makefile 必须另开变更，并以 Windows 手动执行核心任务成功、GitHub required checks 使用 Python 入口成功、文档与外部调用完成迁移为前提。本轮不会自动删除或标记一个未经验证的固定期限。

### 5. CI 直接调用 Python 入口并保持 job 名稳定

GitHub Actions 不再调用 Makefile。`lint` job 依次运行 `format-check` 与 `lint`，其他 job 调用对应 Python 任务。required check 的 job 名称 `lint`、`test`、`package`、`secrets`、`dependencies`、`workflows` 保持不变，避免破坏分支保护。

## Risks / Trade-offs

- [Python 包装层掩盖底层工具能力] → 保持任务薄且命令显式，输出直接透传，并允许开发者继续运行底层 `uv run` 命令排障。
- [Makefile 与 Python 入口再次漂移] → Makefile 只转发任务，不保留底层参数；用契约测试检查 workflow 和 Makefile 引用权威入口。
- [自动修复产生非预期修改] → CI 永远只运行 `format-check`，只有显式 `format` 才修改文件，开发者负责审查 diff。
- [新增 `tools` 代码自身未被检查] → Ruff 格式与 lint 覆盖 `tools`，Pyright 是否覆盖调度模块以实际类型检查兼容性为准并在实施时验证。
- [格式门禁首次启用造成存量失败] → 实施阶段先运行 `format-check`；只对 Ruff formatter 必需的差异做一次机械格式化并单独审查。

## Migration Plan

1. 先用测试定义任务 argv、组合顺序、失败传播和未知任务行为。
2. 实现 Python CI 入口，并在 Windows 手动运行格式、lint、默认测试、安全检查和包验证。
3. 将 Makefile 改成薄兼容层，验证 Make 与 Python 入口结果一致。
4. 将 GitHub workflows 切换到 Python 入口，保持 job 名称和权限不变。
5. 运行全量本地检查并通过 PR 验证 required checks；同步面向开发者的命令文档。
6. 若迁移失败，workflow 和 Makefile 可临时恢复为原底层命令；Python 入口保留供继续修复，不放宽格式或安全门槛。

## Open Questions

无。Makefile 的最终删除时间由后续验证结果和独立变更决定。
