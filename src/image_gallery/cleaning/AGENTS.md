# `cleaning/` 模块指南

## 职责

- 编译清洗配置与算子依赖图，调度参数计算和逻辑评估。
- 管理运行存储、状态恢复、结果归并、导出和预览。
- 不实现具体图片指标算法；指标计算属于 `operators/`。

## 当前能力与公共入口

从 `image_gallery.cleaning` 使用 `BasicCleaner`、`Cleaner`、`CleanerExecution`、`CleanerRecipe`、`CleanerResult`、`ActionRange`、RunStore 类型、`DryRunResult`、`PreviewResult` 和 `evaluate_with_rules`。导出采用惰性加载以避免与 operators 循环导入。

## 核心契约与边界

- Raw Dataset 不可原地修改；clean、dropped、full 只能由 merge policy 生成。
- `clean + dropped = full` 按 `image_id` 集合成立。
- 运行状态由 SQLite/RunStore 管理，图片仍通过 Dataset 与 Storage 访问。
- 逻辑算子名称面向能力，不向用户暴露 OpenCV、fastdup 等实现后端。
- 单张图片计算失败应按策略记录，不能默认终止整个批次。

## 开发与验证

- 单元测试：`tests/unit/cleaning/`
- 集成测试：`tests/integration/cleaning/`
- 当前行为：`openspec/specs/cleaning-runtime/spec.md`、`cleaning-config/spec.md`、`cleaning-preview/spec.md`
- 修改算子契约或参数表时同步检查 `operators/`；修改导出语义时同步检查 `dataset/`。
