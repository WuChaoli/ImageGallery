## MODIFIED Requirements

### Requirement: Python CI lint 统一入口

系统 SHALL 提供 `uv run python -m tools.ci lint` 命令作为 lint 权威入口。该任务 SHALL 依次执行 Ruff check 和 Pyright 检查，任一阻断性检查失败 SHALL 导致非零退出码。Makefile 的 `lint` 目标 SHALL 仅作为兼容别名转发到该入口。GitHub Actions SHALL 在每个面向默认分支的 Pull Request 上调用 Python CI 入口，并将结果配置为 required check。

#### Scenario: Python CI lint 全部通过
- **WHEN** 运行 Python CI `lint` 且代码无任何 Ruff 或 Pyright error
- **THEN** 命令以退出码 0 完成，输出无 error

#### Scenario: Ruff lint 失败
- **WHEN** 运行 Python CI `lint` 且 Ruff 发现违规
- **THEN** 命令以非零退出码退出，输出包含 Ruff 违规详情且不继续执行 Pyright

#### Scenario: Pyright 有 error
- **WHEN** Ruff check 成功但 Pyright 报告 error 级别问题
- **THEN** lint 以非零退出码退出，输出包含 Pyright error 详情

#### Scenario: Pyright 仅有 warning
- **WHEN** Pyright 仅报告 warning 级别问题且无 error
- **THEN** lint 以退出码 0 完成，输出保留 warning

#### Scenario: Makefile 兼容调用
- **WHEN** 开发者运行 `make lint`
- **THEN** Makefile 转发到 Python CI `lint`，不维护独立 Ruff 或 Pyright 参数

#### Scenario: PR lint required check 失败
- **WHEN** GitHub Actions 调用 Python CI 格式检查或 lint 且任一命令返回非零退出码
- **THEN** 名为 `lint` 的 required check 失败并阻止 PR 合并到默认分支

## ADDED Requirements

### Requirement: Ruff 必须作为唯一 Python formatter

系统 SHALL 使用 Ruff formatter 统一格式化仓库维护的 Python 文件，并 MUST NOT 同时引入 Black 或其他会争夺 Python 格式所有权的 formatter。格式范围 SHALL 至少包含 `src/`、`tests/` 和仓库级 Python CI 工具代码。

#### Scenario: 开发者主动格式化
- **WHEN** 开发者运行 Python CI `format`
- **THEN** 系统依次执行 Ruff lint 安全自动修复和 Ruff format，并允许修改范围内文件

#### Scenario: CI 只检查格式
- **WHEN** GitHub Actions 运行 Python CI `format-check`
- **THEN** 系统执行 `ruff format --check` 且不修改 checkout 中的文件

#### Scenario: 文件格式不合规
- **WHEN** `format-check` 发现 Ruff formatter 会修改的 Python 文件
- **THEN** 命令以非零退出码结束并列出需要格式化的文件

### Requirement: check 必须组合只读质量检查

Python CI `check` SHALL 按顺序执行 `format-check`、`lint` 和默认快速测试。`check` MUST NOT 自动修改源码，任一步失败 MUST 停止后续步骤并返回非零退出码。

#### Scenario: 完整本地检查成功
- **WHEN** 代码格式、lint、类型和默认测试均通过
- **THEN** Python CI `check` 以退出码 0 完成且工作树未被该命令修改

#### Scenario: 未格式化代码进入 check
- **WHEN** Python CI `check` 检测到未格式化代码
- **THEN** 命令在执行 lint 和测试前失败，并提示开发者运行 `format`
