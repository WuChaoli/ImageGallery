## 1. 行为护栏

- [x] 1.1 补充 ParameterComputer 深层依赖、配置投影、默认 hash 与冲突错误的 characterization tests
- [x] 1.2 补充 planner、graph 与 dry-run 委托同一私有解析边界的 mutation-style test，并记录 RED
- [x] 1.3 补充 graph 参数节点完整序列与 plan hash 的回归断言

## 2. 私有职责收敛

- [x] 2.1 新增 `_parameter_config.py`，集中依赖闭包、配置投影、hash 与冲突检测
- [x] 2.2 迁移 planner、graph 与 dry-run 到共享 helper，删除重复实现
- [x] 2.3 提取 graph 参数节点装配函数，保持 staged/普通节点顺序与策略语义

## 3. 验证与交付

- [x] 3.1 运行公开 API 契约、目标测试、format、lint、docs 和 OpenSpec strict validate
- [x] 3.2 运行 default test、coverage 与 test-all，确认零失败、source coverage >=90%、diff coverage >=80%
- [x] 3.3 审查 diff、记录行数/复杂度变化并创建中文提交，保持 worktree clean
