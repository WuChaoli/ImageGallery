# `state/` 模块指南

## 职责

- 保留 ImageGallery 顶层运行状态命名空间。
- 当前没有公开状态 API；清洗运行状态仍由 `cleaning/` 内部实现管理。

## 开发边界

- 不要把 cleaning 的 SQLite 或 RunStore 实现机械搬入此命名空间。
- 提升为公共状态 API 前必须通过 OpenSpec 明确所有权、迁移边界和调用方。
- 当前行为：`openspec/specs/state-namespace/spec.md`
