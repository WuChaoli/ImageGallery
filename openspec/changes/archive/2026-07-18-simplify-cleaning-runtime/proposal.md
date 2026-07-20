## Why

`CleaningRuntime` 的新运行与恢复运行分别维护高度重复的计划编译、参数阶段、状态落盘和失败收尾逻辑，增加了认知复杂度，也使两个入口更容易在后续修改中产生持久化语义漂移。现在需要用 characterization tests 固定既有契约，再收敛私有编排实现。

## What Changes

- 为新运行与恢复运行补充 characterization tests，锁定计划执行、参数阶段复用、状态持久化和失败收尾行为。
- 提取两条私有执行路径共享的计划准备、参数阶段和生命周期收尾逻辑，降低 `_run_planned_graph` 与 `_resume_planned_graph` 的重复和认知复杂度。
- 保持公开导出、公开签名、返回值、异常和磁盘持久化语义不变。
- 不修改 `CleanerResult`，不扩展运行时能力，也不引入新的依赖。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `cleaning-runtime`: 明确新运行与恢复运行必须保持一致的运行生命周期、持久化和失败收尾契约。

## Impact

- 影响 `src/image_gallery/cleaning/runtime.py` 的私有实现。
- 增加 `tests/unit/cleaning/` 下的运行时 characterization tests。
- 不影响 `image_gallery.cleaning` 的公开导出、调用方 API、依赖或存储格式。
