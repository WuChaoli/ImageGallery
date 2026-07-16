# code-quality-gates Specification

## Purpose
TBD - created by archiving change strengthen-code-quality-gates. Update Purpose after archive.
## Requirements
### Requirement: Ruff 必须执行精选高确定性规则

系统 SHALL 在现有 Ruff 规则上启用 `S`、`BLE001`、`TRY004`、`PT`、`C901`、`C4`、`SIM102`、`SIM103`、`SIM114`、`SIM115` 和 `RET504`。系统 MUST NOT 通过规则禁止 `for` 循环或强制将循环改为推导式，且 MUST NOT 启用与中文标点规范冲突的 `RUF002/RUF003`。

#### Scenario: 产品代码依赖 assert
- **WHEN** `src/` 中使用 `assert` 承担运行时校验
- **THEN** Ruff 安全检查失败并要求改为显式异常或其他不会被优化移除的校验

#### Scenario: 代码使用清晰 for 循环
- **WHEN** 业务逻辑使用可读的 `for` 循环处理批数据
- **THEN** 质量门禁不因循环未改成推导式而失败

### Requirement: 测试安全豁免必须限定到固有模式

测试目录 SHALL 仅对 pytest `assert`、确定性假凭据和不执行真实不安全临时文件操作的虚拟路径豁免 `S101/S105/S106/S108`。其他安全规则发现 MUST 被修复或按具体行审查，不得对测试目录关闭完整 `S` 规则组。

#### Scenario: 测试使用 pytest assert
- **WHEN** `tests/` 中使用普通 `assert` 验证结果
- **THEN** Ruff 不报告 `S101` 且其他安全规则继续执行

#### Scenario: 测试命中 subprocess 安全规则
- **WHEN** 测试代码命中 `S603` 或其他未列入目录豁免的规则
- **THEN** 检查失败，除非固定 argv 已被验证且存在具体行理由充分的豁免

### Requirement: 宽泛异常只允许存在于隔离边界

普通业务逻辑 MUST NOT 盲捕获 `Exception`。批处理、插件、IO adapter 或调度边界需要隔离第三方失败时 MAY 具体行豁免 `BLE001`，但 MUST 转换、记录、重抛异常或将其写入结构化失败结果，且不得静默吞掉异常。

#### Scenario: 普通函数吞掉异常
- **WHEN** 普通业务函数捕获 `Exception` 后无记录、转换、重抛或失败结果
- **THEN** lint 失败并阻止合并

#### Scenario: 批处理隔离单个损坏输入
- **WHEN** 批处理边界捕获单个输入的第三方异常并记录结构化失败结果，且存在具体 `BLE001` 理由
- **THEN** 该隔离边界允许通过，其他宽泛捕获继续检查

### Requirement: 圈复杂度必须具有温和上限

系统 SHALL 使用 `C901` 将单函数圈复杂度上限设为 15。系统 MUST NOT 使用函数或文件行数作为硬门槛，也不得为降低数字而拆分无独立语义的函数。

#### Scenario: 新增复杂度 16 的函数
- **WHEN** 新增或修改函数的圈复杂度超过 15 且无具体理由豁免
- **THEN** lint 失败并提示拆分职责或说明合理状态边界

#### Scenario: 状态机无法安全拆分
- **WHEN** 集中分支对维护状态一致性必要，且具体函数记录了拆分会降低正确性或可读性的理由
- **THEN** 允许窄粒度 `C901` 豁免

### Requirement: 类型 suppression 必须精确

所有 `type: ignore` 与 `pyright: ignore` MUST 指定具体诊断规则。系统 MUST 禁止无规则 suppression、文件级关闭和未经 OpenSpec 批准降低既有 error 严重度。Pyright error SHALL 阻断，warning SHALL 保持可见但不阻断。

#### Scenario: 无规则类型忽略
- **WHEN** 代码新增 `# type: ignore` 或 `# pyright: ignore` 且未指定诊断规则
- **THEN** 质量检查失败

#### Scenario: pandas stub 产生 warning
- **WHEN** 第三方 stub 产生已知 Pyright warning 且无 error
- **THEN** warning 显示在输出中但不阻断 lint

### Requirement: Any 必须限制在动态边界

系统 SHALL 允许外部 JSON/YAML、pandas、Notebook 或无类型第三方 SDK 边界使用 `Any`，但进入稳定领域逻辑前 MUST 校验或窄化。公共领域 API MUST NOT 仅为逃避类型设计而使用 `Any`。

#### Scenario: 动态 payload 进入核心逻辑
- **WHEN** 外部动态 payload 被传入 Storage、Dataset 或 Cleaning 核心逻辑
- **THEN** 代码在边界完成 schema 校验、类型判断或精确 cast 后再继续处理
