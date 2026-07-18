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

系统 SHALL 使用默认快速测试测量 `src/image_gallery` 覆盖率。全仓源码行覆盖率 MUST 不低于 90.00%，PR 新增或修改的可执行行 diff coverage MUST 不低于 80%。

#### Scenario: PR 新增逻辑缺少测试
- **WHEN** PR 新增可执行业务逻辑且 diff coverage 低于 80%
- **THEN** 覆盖率检查失败并阻止合并

#### Scenario: 文档变更没有可执行行
- **WHEN** PR 仅修改文档或其他无 coverage 信息的文件
- **THEN** diff coverage 检查成功而不是报错

#### Scenario: 全仓覆盖率低于明确底线
- **WHEN** 默认快速测试产生的全仓源码行覆盖率低于 90.00%
- **THEN** 覆盖率检查失败，即使 diff coverage 达到 80%

#### Scenario: 全仓覆盖率达到明确底线
- **WHEN** 默认快速测试产生的全仓源码行覆盖率达到或高于 90.00% 且 diff coverage 达到 80%
- **THEN** 双层覆盖率检查成功

### Requirement: 重构必须执行公开接口契约回归

系统 SHALL 通过默认快速测试冻结公开包导出、可检查的公开调用签名以及 OpenSpec 明确承诺的关键隔离语义。内部私有模块与私有符号不属于稳定接口，MUST NOT 因契约测试而被强制保留。

#### Scenario: 重构修改公开导出
- **WHEN** 重构删除、重命名或新增包级 `__all__` 导出但未形成明确的产品行为变更
- **THEN** 公开接口契约测试失败并阻止合并

#### Scenario: 重构修改公开签名
- **WHEN** 重构改变已导出函数、类或方法的可检查调用签名
- **THEN** 公开接口契约测试失败并指出发生漂移的符号

#### Scenario: 重构移动私有实现
- **WHEN** 重构仅移动或拆分未公开的内部模块、私有函数或私有类且公开契约保持一致
- **THEN** 公开接口契约测试继续成功

#### Scenario: Cleaning 惰性导入保持语义
- **WHEN** 调用方访问 `image_gallery.cleaning` 的任一公开惰性导出或未知名称
- **THEN** 公开导出解析为原对象，未知名称继续抛出 `AttributeError`

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
