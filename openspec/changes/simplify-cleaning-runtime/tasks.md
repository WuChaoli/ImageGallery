## 1. Characterization Tests

- [x] 1.1 补充新计划运行的参数阶段、running/completed 快照和事件顺序测试
- [x] 1.2 补充恢复运行复用 completed 参数节点并保留 started_at 的测试
- [x] 1.3 补充新运行和恢复运行失败后的表、JSON、SQLite 与事件收尾测试
- [x] 1.4 通过受控 mutation 验证新增测试会在生命周期语义被破坏时失败

## 2. Runtime Simplification

- [x] 2.1 引入模块私有运行会话对象，集中计划、上下文、路径和可变快照数据
- [x] 2.2 提取共享参数阶段与 running 状态持久化流程
- [x] 2.3 提取共享成功衔接和失败收尾流程，简化 `_run_planned_graph` 与 `_resume_planned_graph`
- [x] 2.4 保持新运行初始化、恢复状态加载和 completed 节点复用差异清晰可见

## 3. Verification

- [x] 3.1 运行 cleaning runtime 目标测试并确认零失败
- [x] 3.2 运行适用的 `test-all`、lint、format-check 和 OpenSpec validate
- [x] 3.3 验证最终 coverage 不低于 90%，diff coverage 不低于 80%
- [x] 3.4 审查公开导出、签名、返回值、异常和持久化格式均未改变
