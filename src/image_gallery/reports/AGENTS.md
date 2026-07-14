# `reports/` 模块指南

## 职责

- 保留清洗和数据集报告命名空间。
- 当前没有公开报告 API 或生成实现。

## 开发边界

- 不要把 CleanerResult 的现有输出包装成未经设计的新公共 API。
- 新增报告能力前先定义输入数据、输出格式和与 visualization 的边界。
- 当前行为：`openspec/specs/reports/spec.md`
