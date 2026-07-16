## ADDED Requirements

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
