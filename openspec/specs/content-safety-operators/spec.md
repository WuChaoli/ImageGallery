# content-safety-operators Specification

## Purpose
TBD - created by archiving change add-future-capability-placeholders. Update Purpose after archive.
## Requirements
### Requirement: 内容安全算子扩展（PLANNED）
系统 SHALL 在未来扩展内容安全类清洗算子，包括 NSFW 检测、水印检测、文字图片检测等。

#### Scenario: 算子存在性
- **WHEN** 检查内容安全算子
- **THEN** 算子不存在（尚未实现，当前为占位 spec）

#### Scenario: 计划算子列表
- **WHEN** 未来实现内容安全算子
- **THEN** 计划包含：content.nsfw_check（NSFW 检测）、content.watermark_check（水印检测）、content.text_image_check（文字图片检测）

#### Scenario: 与 operators 模块的关系
- **WHEN** 内容安全算子实现后
- **THEN** SHALL 注册到 OperatorRegistry，使用与现有算子相同的 OperatorSpec + ParameterComputer 架构

#### Scenario: 模型依赖
- **WHEN** 内容安全算子需要深度学习模型
- **THEN** 模型 SHALL 作为可选依赖（extras），缺失时在 before_run_check 阶段给出明确错误

#### Scenario: V1 不实现
- **WHEN** 检查 V1 范围
- **THEN** 内容安全算子不在 V1 实现范围内

