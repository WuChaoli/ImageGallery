## ADDED Requirements

### Requirement: make lint 统一入口

系统 SHALL 提供 `make lint` 命令作为所有静态检查的统一入口。`make lint` SHALL 依次执行 ruff check 和 pyright 检查，任一阻断性检查失败 SHALL 导致非零退出码。

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
