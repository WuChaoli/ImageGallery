## ADDED Requirements

### Requirement: utils 跨模块工具命名空间
系统 SHALL 提供 `utils` 模块作为跨模块复用小工具的命名空间，只放置真正被多个领域模块共享的辅助函数，不承载业务逻辑。

#### Scenario: 模块存在性
- **WHEN** 检查 `image_gallery.utils` 包
- **THEN** 模块存在且可导入

#### Scenario: 当前状态为空命名空间
- **WHEN** 检查 utils 模块内容
- **THEN** 当前只包含 `__init__.py` 命名空间声明，无实质实现代码

#### Scenario: 未来扩展约束
- **WHEN** 向 utils 模块添加新工具函数
- **THEN** 该函数 SHALL 被至少两个不同领域模块引用，否则不应放入 utils 而应留在使用方模块内部
