## MODIFIED Requirements

### Requirement: Agent provides direct runnable commands

AI Agent SHALL 仅提供跨平台 `uv run python -m tools.ci <task>` 开发命令。默认测试任务 SHALL 排除 `slow` 测试，并 SHALL 提供独立的真实数据验收与完整测试任务。

#### Scenario: Agent references default test command
- **WHEN** Agent 引用默认测试命令
- **THEN** Agent SHALL 提供 `uv run python -m tools.ci test`

#### Scenario: Agent references real dataset test command
- **WHEN** Agent 引用真实数据验收命令
- **THEN** Agent SHALL 提供 `uv run python -m tools.ci test-real`

#### Scenario: Agent references lint command
- **WHEN** Agent 引用 lint 命令
- **THEN** Agent SHALL 提供 `uv run python -m tools.ci lint`

#### Scenario: Agent references obsolete Make command
- **WHEN** Agent 准备提供 `make` 开发命令
- **THEN** Agent SHALL 改用对应的 Python CI 任务
