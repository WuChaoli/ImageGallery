## Why

当前仓库默认测试已全部通过，但全仓源码行覆盖率仅为 89.75%，公开 API 稳定性也主要依赖分散测试与人工审查，无法为跨模块、分阶段重构提供足够明确的回归护栏。现在需要先建立可执行的接口契约和 90% 覆盖率底线，再安全推进整个项目的内部简化。

## What Changes

- 将默认快速测试测得的全仓源码行覆盖率门槛从 89% 提升到 90%。
- 新增公开包导出、关键签名、异常和新旧平台隔离语义的契约测试。
- 明确重构期间已执行测试必须全部通过，覆盖率不得通过排除业务模块或无依据豁免来提高。
- 建立全项目按风险递增、每阶段独立 OpenSpec、分支和 PR 的重构路线图。
- 本 change 不修改产品功能、公开 API、默认值、返回语义或错误处理结果。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `test-quality-gates`: 将全仓源码行覆盖率底线明确为 90%，并要求公开接口契约回归测试阻止重构引入的语义漂移。

## Impact

- 测试：新增包级公开接口和关键领域边界契约测试。
- 工具：调整 `tools.ci coverage` 的全仓覆盖率门槛。
- CI：现有 coverage required check 将执行更严格的 90% 门槛，不新增外部服务依赖。
- 后续开发：Cleaning、Operators、旧数据链路、新平台基础设施与 DatasetManager 将分别通过独立 change 和 PR 实施。
- 公开 API 与运行时：无行为变化，无 breaking change。
