# `config/` 模块指南

## 职责

- 保留 ImageGallery 顶层配置命名空间。
- 当前没有公开配置对象或业务实现。

## 开发边界

- 不要仅为未来可能的需求预先增加抽象。
- 新增公共配置前先创建或更新 OpenSpec change，并明确它为何不属于现有模块配置。
- 当前行为：`openspec/specs/config-namespace/spec.md`
