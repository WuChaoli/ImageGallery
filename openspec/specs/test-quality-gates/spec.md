# test-quality-gates Specification

## Purpose
TBD - created by archiving change strengthen-code-quality-gates. Update Purpose after archive.
## Requirements
### Requirement: pytest 配置必须严格

pytest SHALL 启用 strict markers 与 strict config，Ruff SHALL 对测试执行完整 `PT` 规则组。异常断言 MUST 使用稳定语义片段，而不是绑定易变的完整异常文案。

#### Scenario: marker 拼写错误
- **WHEN** 测试使用未注册或拼写错误的 marker
- **THEN** 默认测试失败而不是仅输出 warning

#### Scenario: 异常断言过宽
- **WHEN** 测试只断言宽泛异常类型而不能区分预期错误原因
- **THEN** pytest 风格检查失败并要求更具体异常或稳定 `match`

### Requirement: 覆盖率必须同时防止全仓回退和未测试变更

系统 SHALL 使用默认快速测试测量 `src/image_gallery` 覆盖率。全仓覆盖率 MUST 不低于实施时测得的稳定基线向下取整值，PR 新增或修改的可执行行 diff coverage MUST 不低于 80%。

#### Scenario: 新增逻辑没有测试
- **WHEN** PR 新增可执行业务逻辑且 diff coverage 低于 80%
- **THEN** 覆盖率检查失败并阻止合并

#### Scenario: PR 不含可执行 Python 变更
- **WHEN** PR 仅修改文档或配置且没有可计算的 Python 可执行行
- **THEN** diff coverage 检查成功而不是报错

#### Scenario: 全仓覆盖率明显回退
- **WHEN** 默认快速测试产生的全仓覆盖率低于已确认基线
- **THEN** 覆盖率检查失败，即使 diff coverage 达到 80%

### Requirement: 覆盖率豁免必须窄且有理由

`pragma: no cover` MUST 仅用于普通测试环境确实无法触发的防御性或平台分支，并 SHALL 记录具体理由。系统 MUST NOT 排除完整业务模块以提高覆盖率数字。

#### Scenario: 整个模块被排除
- **WHEN** coverage 配置试图排除 Storage、Dataset、Cleaning 或其他完整业务模块
- **THEN** 配置治理检查失败

### Requirement: 默认测试必须保持快速确定

普通 PR SHALL 运行固定顺序的默认快速测试，继续排除 `slow` 与 `real_dataset`。随机顺序、重复测试和 mutation testing MUST NOT 加入普通 PR required check。

#### Scenario: 普通 PR 测试
- **WHEN** PR 执行默认测试
- **THEN** 测试使用固定本地 fixture、禁止意外网络且不连接 MinIO

### Requirement: 深度测试必须进入定时或手动巡检

定时巡检 SHALL 使用可复现 seed 随机化测试顺序，并 SHALL 将 `stability` 测试重复 5 次。Vulture 高置信度、外部 warning 和核心纯逻辑 mutation testing SHALL 先报告而不阻断普通 PR。

#### Scenario: 随机顺序测试失败
- **WHEN** 定时随机测试发现顺序依赖
- **THEN** 结果记录失败测试与 seed，使开发者可本地复现

#### Scenario: 稳定性测试偶发失败
- **WHEN** 标记为 `stability` 的测试在 5 次重复中任一次失败
- **THEN** 定时任务报告具体轮次和测试名称
