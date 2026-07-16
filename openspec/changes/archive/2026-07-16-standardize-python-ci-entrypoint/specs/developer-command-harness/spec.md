## ADDED Requirements

### Requirement: 仓库必须提供跨平台 Python CI 入口

系统 SHALL 提供可通过 `uv run python -m tools.ci <task>` 调用的仓库级命令入口。该入口 MUST 在 Windows 与 Linux 上使用相同任务名称和底层参数，且不得依赖 GNU Make 或平台特定 shell 语法。

#### Scenario: Windows 执行 lint
- **WHEN** 开发者在已同步 uv 环境的 Windows checkout 中运行 Python CI 的 `lint` 任务
- **THEN** 系统执行 Ruff lint 和 Pyright，并返回底层检查结果

#### Scenario: 请求未知任务
- **WHEN** 开发者向 Python CI 入口传入未定义的任务名称
- **THEN** 系统输出可用任务提示并以非零退出码结束，且不执行任意外部命令

### Requirement: 组合任务必须透明传播失败

系统 SHALL 使用固定参数列表启动底层工具且 MUST NOT 使用 `shell=True`。组合任务 MUST 按契约顺序执行，并在首个子任务失败时停止并返回非零退出码。

#### Scenario: 格式检查失败
- **WHEN** `check` 任务执行 `format-check` 时发现未格式化文件
- **THEN** `check` 立即失败，不继续执行 lint 或测试，并向终端保留 Ruff 原始诊断

#### Scenario: 所有子任务成功
- **WHEN** 组合任务中的所有子任务均返回成功
- **THEN** Python CI 入口以退出码 0 结束

### Requirement: Makefile 必须作为兼容层保留

本变更期间 Makefile SHALL 保留现有开发目标，并 SHALL 将目标转发到对应 Python CI 任务，而不是维护重复的底层工具参数。系统 MUST NOT 在 Windows 手动验证和 GitHub CI 验证完成前删除 Makefile。

#### Scenario: 使用旧 Make 入口
- **WHEN** 已安装 GNU Make 的开发者运行现有 `make lint`
- **THEN** Makefile 调用 Python CI 的 `lint` 任务并返回相同检查结果

#### Scenario: Python 入口尚未完成验证
- **WHEN** Windows 手动测试或 GitHub required check 尚未证明 Python CI 入口可用
- **THEN** Makefile 继续保留且不得作为本变更的一部分删除

### Requirement: 测试任务必须保持数据分层

Python CI 入口 SHALL 保持默认快速测试、完整测试和真实数据验收相互独立。默认 `test` MUST 排除 `slow` 与 `real_dataset`，真实数据任务 MUST 显式执行且不得合并到普通 PR 默认测试。

#### Scenario: 运行默认测试
- **WHEN** 开发者或 CI 调用 Python CI 的 `test` 任务
- **THEN** 系统使用固定本地 fixture 执行快速测试，不连接 MinIO 或加载 sample_1000

#### Scenario: 运行真实数据验收
- **WHEN** 开发者显式调用 Python CI 的 `test-real` 任务
- **THEN** 系统仅执行标记为 `real_dataset` 的验收测试
