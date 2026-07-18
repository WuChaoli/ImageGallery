## Why

Cleaning planning 与 dry-run 各自实现了 ParameterComputer 依赖闭包、配置投影、hash 和冲突检测，重复逻辑容易在后续调整中产生语义漂移。graph 的参数节点构造同时承担配置合并、运行策略解析和节点装配，增加了验证计划顺序与 hash 稳定性的成本。

## What Changes

- 以 characterization tests 固定依赖闭包、配置投影、默认 hash、冲突异常、计划/节点顺序及运行策略 hash。
- 提取 cleaning 私有配置解析职责，由 planner 与 dry-run 共享同一实现。
- 收敛 graph 参数节点构造边界，保持节点内容、顺序、hash 与运行状态语义不变。
- 不新增或修改公共 API，不改变 SQLite schema、失败恢复、hook 或产物语义。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `cleaning-runtime`: 把 planning、graph 与 dry-run 对 ParameterComputer 配置解析的一致性固化为可验证契约；对外行为保持不变。

## Impact

主要影响 `image_gallery.cleaning` 的私有 planning/dry-run/graph 实现及其单元测试。无新增依赖，不影响公开导出、调用签名或持久化格式。
