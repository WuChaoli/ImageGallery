# Design: digest-docs-design-decisions

## Context

docs/ 目录包含项目从 PRD 到架构到模块设计的完整文档体系。这些文档先于代码编写，部分设计已被后续迭代（V1→V2→V3）超越。当前 openspec/specs/ 是从代码逆向生成的行为契约，但缺少一些尚未实现但仍有效的设计约束。

## Goals

- 把 docs/ 中仍然有效的设计决策增补到 openspec specs
- 确保 image_uri 唯一引用、clean+dropped=full 等核心不变量在 spec 中有显式记录
- 补充 URL 导入安全边界和导入模式策略等尚未实现但已规划的需求

## Non-Goals

- 不替代 docs/architecture/modules/ 中的详细设计文档
- 不迁移开发计划或实现步骤

## Key Decisions

### D1: 只增补行为契约，不复制设计文档

docs/ 中的详细设计（如 536 行的清洗平台设计、533 行的错误处理设计）保持原位。openspec specs 只增加可测试的 WHEN/THEN 场景，不复制设计动机和对象模型。

### D2: 核心不变量放在 cleaning-runtime spec

image_uri 唯一引用、clean+dropped=full、raw Dataset 不可变等约束虽然跨模块，但 cleaning-runtime 是这些约束最集中的验证点。放在此处可确保每次清洗运行时变更都检查这些不变量。

### D3: URL 安全边界作为 PLANNED 需求标记

URL 导入安全边界（拒绝内网地址、限制重定向等）已在架构文档中设计但尚未实现。在 spec 中标记为 PLANNED，明确这是已知需求。

## Risks

- **[Spec 与 docs 重复]** → openspec 只记录可测试契约，设计解释留在 docs/
- **[PLANNED 需求长期未实现]** → 后续 change 应定期回顾 PLANNED 标记
