## MODIFIED Requirements

### Requirement: make lint 统一入口

系统 SHALL 提供 `make lint` 命令作为所有静态检查的统一入口。`make lint` SHALL 依次执行 ruff check 和 pyright 检查，任一阻断性检查失败 SHALL 导致非零退出码。GitHub Actions SHALL 在每个面向默认分支的 Pull Request 上调用与该入口等价的检查，并将结果配置为 required check。

#### Scenario: make lint 全部通过

- **WHEN** 运行 `make lint` 且代码无任何 ruff 或 pyright error
- **THEN** 命令以退出码 0 完成，输出无 error

#### Scenario: make lint ruff 失败

- **WHEN** 运行 `make lint` 且 ruff 发现违规（如 import 排序错误、缺失 docstring）
- **THEN** 命令以非零退出码退出，输出包含 ruff 违规详情

#### Scenario: make lint pyright 有 error

- **WHEN** 运行 `make lint` 且 pyright 报告 error 级别问题（如缺失参数类型标注）
- **THEN** 命令以非零退出码退出，输出包含 pyright error 详情

#### Scenario: make lint pyright 仅有 warning

- **WHEN** 运行 `make lint` 且 pyright 仅报告 warning 级别问题（如显式 Any 使用），无 error
- **THEN** 命令以退出码 0 完成，输出包含 warning 但不阻断

#### Scenario: PR lint required check 失败

- **WHEN** GitHub Actions 在 Pull Request 上运行统一 lint 入口且命令返回非零退出码
- **THEN** lint required check 失败并阻止该 PR 合并到默认分支
