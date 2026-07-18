## MODIFIED Requirements

### Requirement: Python CI lint 统一入口

系统 SHALL 提供 `uv run python -m tools.ci lint` 命令作为唯一 lint 权威入口。该任务 SHALL 依次执行 Ruff check 和 Pyright 检查，任一阻断性检查失败 SHALL 导致非零退出码。GitHub Actions SHALL 在每个面向默认分支的 Pull Request 上调用 Python CI 入口，并将结果配置为 required check。

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

#### Scenario: PR lint required check 失败
- **WHEN** GitHub Actions 调用 Python CI 格式检查或 lint 且任一命令返回非零退出码
- **THEN** 名为 `lint` 的 required check 失败并阻止 PR 合并到默认分支

### Requirement: pyright 类型检查配置

系统 SHALL 使用 pyright 作为静态类型检查器，替代 mypy。pyright SHALL 配置为 strict 模式。Any 相关规则 SHALL 设为 warning 严重性，不阻断 lint。缺失类型标注 SHALL 设为 error 严重性，阻断 lint。

#### Scenario: 缺失参数类型标注阻断 lint
- **WHEN** 公开函数的参数缺少类型标注并运行 Python CI `lint`
- **THEN** Pyright 报告 error，lint 以非零退出码退出

#### Scenario: 显式 Any 使用不阻断 lint
- **WHEN** 函数签名中使用 `Any` 类型并运行 Python CI `lint`
- **THEN** Pyright 报告 warning 但 lint 以退出码 0 完成

#### Scenario: 隐式 unknown 类型不阻断 lint
- **WHEN** 变量或参数推断为 unknown 类型并运行 Python CI `lint`
- **THEN** Pyright 报告 warning 但 lint 以退出码 0 完成

### Requirement: ruff docstring 检查规则

系统 SHALL 通过 Ruff D 规则组强制检查公开函数、类和方法的 docstring 存在性与格式。不以 `_` 开头的公开 class、method 和 function MUST 有 docstring。测试文件 SHALL 豁免所有 D 规则。

#### Scenario: 公开函数缺少 docstring
- **WHEN** 不以 `_` 开头的公开函数没有 docstring 并运行 Python CI `lint`
- **THEN** Ruff 报告 D103 违规，lint 以非零退出码退出

#### Scenario: 私有函数不需要 docstring
- **WHEN** 以 `_` 开头的私有函数没有 docstring 并运行 Python CI `lint`
- **THEN** Ruff 不报告 D 规则违规

#### Scenario: 测试文件豁免 docstring 检查
- **WHEN** `tests/` 目录下的测试函数没有 docstring 并运行 Python CI `lint`
- **THEN** Ruff 不报告 D 规则违规

### Requirement: AGENTS.md 规范同步

AGENTS.md SHALL 将 Python CI 记录为唯一 lint 入口，并 SHALL 明确所有不以 `_` 开头的公开函数、类和方法必须有 docstring。

#### Scenario: AGENTS.md 命令段落更新
- **WHEN** 查阅 AGENTS.md 的构建、测试和 lint 命令段落
- **THEN** 文档只提供 `uv run python -m tools.ci` 入口且不提供 Make 命令

#### Scenario: AGENTS.md docstring 规范更新
- **WHEN** 查阅 AGENTS.md 的 docstring 规范段落
- **THEN** 文档明确所有公开函数必须有 docstring
