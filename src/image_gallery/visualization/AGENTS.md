# `visualization/` 模块指南

## 职责

- 为 Notebook 和交互环境渲染 Dataset/DataFrame 图片网格。
- 不拥有 Dataset、Storage 或清洗结果的持久化状态。

## 当前能力与公共入口

从 `image_gallery.visualization` 使用 `render_image_grid` 和 `show_image_grid`。

## 核心契约与边界

- 图片内容必须通过 Dataset 或受支持 URI 读取，不绕过 Storage 约束。
- HTML 输出必须可安全嵌入 Notebook；用户字段需要正确转义。
- 布局与展示变化不得改变 Dataset 内容。

## 开发与验证

- 单元测试：`tests/unit/visualization/`
- 当前行为：`openspec/specs/visualization/spec.md`
- 清洗结果预览策略另见 `openspec/specs/cleaning-preview/spec.md`。
