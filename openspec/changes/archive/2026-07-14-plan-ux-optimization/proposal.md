# Proposal: plan-ux-optimization

## Summary

将 superpowers/ 中的 `cleaning-user-experience-optimization` 计划（1208 行）完整转化为 openspec change，覆盖短名算子迁移、YAML Recipe 系统、非阻塞运行模型、RunStore 存储模式、MetricSpec 元数据、批量导出和 before_run_check 钩子共 7 个功能域。这些功能均为计划但未实现的下一批开发方向。

## Added Capabilities

- 新增 cleaning-operators spec 的短名算子命名需求（17 个算子从 `category.operator_check` 迁移为短名）
- 新增 cleaning-config spec 的 YAML Recipe 系统需求（CleanerRecipe.from_yaml、ActionRange 区间规则）
- 新增 cleaning-config spec 的 MetricSpec 元数据需求（absolute/relative/categorical 阈值分类）
- 新增 cleaning-runtime spec 的非阻塞运行模型需求（run→CleanerRun、run_sync→CleanerResult、stop/progress）
- 新增 cleaning-runtime spec 的 RunStore 存储模式需求（memory/temporary/disk 三种模式）
- 新增 cleaning-preview spec 的 export("ALL") 批量导出需求
- 新增 cleaning-runtime spec 的 before_run_check 生命周期钩子需求

## Modified Capabilities

- `cleaning-operators`: 算子命名从长名迁移为短名（破坏式变更）
- `cleaning-config`: 新增 YAML Recipe 和 MetricSpec 两个子系统
- `cleaning-runtime`: 运行模型从阻塞式改为非阻塞式，新增 RunStore 和生命周期钩子
- `cleaning-preview`: 导出 API 增加批量导出和默认列契约

## Affected Specs

- `specs/cleaning-operators/spec.md`
- `specs/cleaning-config/spec.md`
- `specs/cleaning-runtime/spec.md`
- `specs/cleaning-preview/spec.md`

## Non-Goals

- 不实现代码变更
- 不实现重复图保留策略增强（后续）
- 不实现 training/export 节点（YOLO/COCO/LabelImg 导出，后续）
- 不引入服务端 API 或 Web UI
