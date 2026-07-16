## Purpose
定义仓库 lint 统一入口、pyright 类型检查、ruff docstring 规则和 AGENTS.md 工具链同步要求。
## Requirements
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

### Requirement: pyright 类型检查配置

系统 SHALL 使用 pyright 作为静态类型检查器，替代 mypy。pyright SHALL 配置为 strict 模式。Any 相关规则（reportAny、reportUnknownVariableType、reportUnknownArgumentType、reportUnknownMemberType、reportMissingTypeArgument）SHALL 设为 warning 严重性，不阻断 lint。缺失类型标注（reportMissingParameterType）SHALL 设为 error 严重性，阻断 lint。

#### Scenario: 缺失参数类型标注阻断 lint

- **WHEN** 公开函数的参数缺少类型标注，运行 `make lint`
- **THEN** pyright 报告 error，lint 以非零退出码退出

#### Scenario: 显式 Any 使用不阻断 lint

- **WHEN** 函数签名中使用 `Any` 类型，运行 `make lint`
- **THEN** pyright 报告 warning 但 lint 以退出码 0 完成

#### Scenario: 隐式 unknown 类型不阻断 lint

- **WHEN** 变量或参数推断为 unknown 类型（来自未标注的第三方库返回值），运行 `make lint`
- **THEN** pyright 报告 warning 但 lint 以退出码 0 完成

### Requirement: ruff docstring 检查规则

系统 SHALL 通过 ruff D 规则组强制检查公开函数/类/方法的 docstring 存在性与格式。不以 `_` 开头的公开 class（D101）、method（D102）、function（D103）MUST 有 docstring。docstring 格式 SHALL 符合 D205（summary 与描述间空一行）、D300（三引号）、D400（首行以句号结尾）规则。测试文件（`tests/**`）SHALL 豁免所有 D 规则。

#### Scenario: 公开函数缺少 docstring

- **WHEN** 不以 `_` 开头的公开函数没有 docstring，运行 `make lint`
- **THEN** ruff 报告 D103 违规，lint 以非零退出码退出

#### Scenario: 简单 getter 也需要 docstring

- **WHEN** 一个不以 `_` 开头的公开 getter 函数（如 `def get_uri(self) -> str: return self._uri`）没有 docstring
- **THEN** ruff 报告 D103 违规，该函数 MUST 补充 docstring 才能通过 lint

#### Scenario: 私有函数不需要 docstring

- **WHEN** 以 `_` 开头的私有函数没有 docstring，运行 `make lint`
- **THEN** ruff 不报告 D 规则违规

#### Scenario: 测试文件豁免 docstring 检查

- **WHEN** `tests/` 目录下的测试函数没有 docstring，运行 `make lint`
- **THEN** ruff 不报告 D 规则违规（per-file-ignores 豁免）

#### Scenario: docstring 格式不合规

- **WHEN** 公开函数有 docstring 但首行不以句号结尾，运行 `make lint`
- **THEN** ruff 报告 D400 违规，lint 以非零退出码退出

### Requirement: AGENTS.md 规范同步

AGENTS.md SHALL 反映工具链变更：删除 mypy 命令，新增 pyright 和 `make lint` 命令。docstring 规范段落 SHALL 取消"简单 getter 可不写 docstring"的例外，明确所有不以 `_` 开头的公开函数/类/方法必须有 docstring。

#### Scenario: AGENTS.md 命令段落更新

- **WHEN** 查阅 AGENTS.md 的构建/测试/lint 命令段落
- **THEN** 不包含 mypy 命令，包含 `make lint` 和 `python -m pyright src/image_gallery` 命令

#### Scenario: AGENTS.md docstring 规范更新

- **WHEN** 查阅 AGENTS.md 的 docstring 规范段落
- **THEN** 不包含"简单 getter 可不写 docstring"的例外，明确所有公开函数（不以 `_` 开头）必须有 docstring

### Requirement: lint 入口必须包含精选规则与 suppression 治理

统一 lint 入口 SHALL 执行已批准的精选 Ruff 规则、圈复杂度 15 上限、完整 pytest `PT` 规则和 Pyright strict error 检查。入口 SHALL 同时拒绝无具体规则的 Ruff、Pyright 与 type ignore suppression。

#### Scenario: lint 发现宽泛 suppression
- **WHEN** 源码新增 `# noqa`、无规则 `# type: ignore` 或无规则 `# pyright: ignore`
- **THEN** lint 失败并要求限定到具体诊断

#### Scenario: Pyright 只有 warning
- **WHEN** lint 的 Pyright 阶段仅产生 warning 且无 error
- **THEN** warning 保持可见，统一 lint 入口以成功状态结束

### Requirement: lint 规则不得与项目语言规范冲突

lint 配置 MUST 保留中文注释和 docstring 的全角标点，并 MUST NOT 通过简化规则禁止 `for` 循环、强制三元表达式或强制将所有异常消息抽取为自定义异常。

#### Scenario: 中文 docstring 使用逗号
- **WHEN** 中文 docstring 使用全角逗号或括号
- **THEN** lint 不报告 `RUF002/RUF003`

#### Scenario: if else 比三元表达式更清晰
- **WHEN** 多行 `if/else` 表达边界条件比三元表达式更可读
- **THEN** lint 不因 `SIM108` 强制改写
