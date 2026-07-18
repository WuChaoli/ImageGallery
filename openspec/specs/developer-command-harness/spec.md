## Purpose

定义仓库跨平台 Python CI 命令入口、固定参数与组合任务失败传播规则、PR 创建或更新前的拆分式手动验证策略，以及默认、完整和真实数据测试的分层边界。

## Requirements

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

### Requirement: 组合任务必须透明传播失败

系统 SHALL 使用固定参数列表启动底层工具且 MUST NOT 使用 `shell=True`。组合任务 MUST 按契约顺序执行，并在首个子任务失败时停止并返回非零退出码。

#### Scenario: 格式检查失败
- **WHEN** `check` 任务执行 `format-check` 时发现未格式化文件
- **THEN** `check` 立即失败，不继续执行 lint 或测试，并向终端保留 Ruff 原始诊断

#### Scenario: 所有子任务成功
- **WHEN** 组合任务中的所有子任务均返回成功
- **THEN** Python CI 入口以退出码 0 结束

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

### Requirement: 测试任务必须保持数据分层

Python CI 入口 SHALL 保持默认快速测试、完整测试、真实数据验收和 DatasetManager Backend 容器验收相互独立。默认 `test` MUST 排除 `slow` 与 `dataset_backend`，`test-all` MUST 排除 `dataset_backend`，真实数据与 Backend 任务 MUST 显式执行且不得合并到普通 PR 默认测试。

#### Scenario: 运行默认测试
- **WHEN** 开发者或 CI 调用 Python CI 的 `test` 任务
- **THEN** 系统使用固定本地 fixture 执行快速测试，不连接 MinIO 或加载 sample_1000

#### Scenario: 运行真实数据验收
- **WHEN** 开发者显式调用 Python CI 的 `test-real` 任务
- **THEN** 系统仅执行标记为 `real_dataset` 的验收测试

#### Scenario: 运行 DatasetManager Backend 验收
- **WHEN** 开发者显式调用 Python CI 的 `dataset-backend` 任务
- **THEN** 系统仅执行 DatasetManager 中标记为 `dataset_backend` 的容器验收测试
