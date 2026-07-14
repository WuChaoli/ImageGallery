# Proposal: digest-docs-design-decisions

## Summary

将 docs/ 中仍然有效的设计决策沉淀到 openspec specs 中，包括图片导入的安全边界、导入模式策略和贯穿全系统的核心不变量。同时标记 docs/ 中已过时的旧设计文档状态。

## Added Capabilities

- 新增 image-import spec 的 URL 导入安全边界需求（安全白名单、拒绝内网/元数据地址、重定向限制等）
- 新增 image-import spec 的导入模式策略需求（copy / reference / copy_on_write）
- 新增 cleaning-runtime spec 的核心不变量需求（image_uri 唯一引用、clean+dropped=full、raw Dataset 不可变等）
- 新增 storage-system spec 的受管输出路径约束需求（拒绝路径逃逸、原子提交语义）

## Modified Capabilities

- `image-import`: 补充 URL 安全边界和导入模式策略场景
- `cleaning-runtime`: 补充核心不变量和跨模块约束场景
- `storage-system`: 补充受管路径安全约束场景

## Affected Specs

- `specs/image-import/spec.md`
- `specs/cleaning-runtime/spec.md`
- `specs/storage-system/spec.md`

## Non-Goals

- 不实现代码变更
- 不迁移 docs/development/ 中的分阶段开发计划
- 不处理 superpowers/ 中的内容（由 plan-ux-optimization change 负责）
- 不删除或修改 docs/ 下的文件（仅标记状态）
