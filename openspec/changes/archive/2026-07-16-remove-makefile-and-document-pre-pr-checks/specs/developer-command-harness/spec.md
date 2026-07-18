## MODIFIED Requirements

### Requirement: 仓库必须提供跨平台 Python CI 入口

系统 SHALL 仅提供可通过 `uv run python -m tools.ci <task>` 调用的仓库级命令入口。该入口 MUST 在 Windows 与 Linux 上使用相同任务名称和底层参数，且不得依赖 GNU Make 或平台特定 shell 语法。当前权威文档、规范和测试 MUST NOT 提供 Makefile 兼容入口。

#### Scenario: Windows 执行 lint
- **WHEN** 开发者在已同步 uv 环境的 Windows checkout 中运行 Python CI 的 `lint` 任务
- **THEN** 系统执行 Ruff lint 和 Pyright，并返回底层检查结果

#### Scenario: 请求未知任务
- **WHEN** 开发者向 Python CI 入口传入未定义的任务名称
- **THEN** 系统输出可用任务提示并以非零退出码结束，且不执行任意外部命令

#### Scenario: 检查仓库命令入口
- **WHEN** 治理测试检查根目录和当前权威文档
- **THEN** 根 Makefile 不存在且内容不提供 `make` 开发命令

## ADDED Requirements

### Requirement: PR 前验证必须逐项执行

开发者在创建或更新 PR 前 SHALL 依次运行 Python CI 的 `format-check`、`lint`、`docs`、`test`、`coverage`、`security`、`package`、`package-validate` 和 `package-smoke` 任务。每项 MUST 独立执行；任一任务失败时 MUST 停止后续验证并先修复失败。所有必跑任务返回 0 后才可创建或更新 PR。

#### Scenario: lint 阶段失败
- **WHEN** `format-check` 成功但独立 `lint` 任务返回非零退出码
- **THEN** 开发者停止验证并修复 lint，不等待测试、安全或包验证完成

#### Scenario: 所有必跑任务成功
- **WHEN** PR 前清单中的每项独立任务均返回 0
- **THEN** 变更满足本地 PR 前手动验证要求

#### Scenario: 日常 check 成功
- **WHEN** `tools.ci check` 成功但完整 PR 前清单尚未逐项执行
- **THEN** 开发者不得将 `check` 结果视为完整 PR 前验证

## REMOVED Requirements

### Requirement: Makefile 必须作为兼容层保留

**Reason**: Python CI 入口已经完成 Windows、Linux 与真实 PR 验证，双入口只会增加维护和契约漂移。

**Migration**: 将所有 `make <target>` 调用替换为 `uv run python -m tools.ci <task>`。
