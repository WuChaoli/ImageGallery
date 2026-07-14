## ADDED Requirements

### Requirement: state 运行状态命名空间
系统 SHALL 提供 `state` 模块作为跨模块运行状态管理的命名空间，用于存放非清洗领域专用的状态存储接口。

#### Scenario: 模块存在性
- **WHEN** 检查 `image_gallery.state` 包
- **THEN** 模块存在且可导入

#### Scenario: 当前状态为空命名空间
- **WHEN** 检查 state 模块内容
- **THEN** 当前只包含 `__init__.py` 命名空间声明，无实质实现代码

#### Scenario: 清洗运行状态归属
- **WHEN** 查找清洗运行状态存储实现
- **THEN** 清洗领域的运行状态 SHALL 在 cleaning 模块内实现（JsonRunStateStore 和 CleanerRunState 在 `cleaning/state.py`，SQLiteRunStateStore 在 `cleaning/runtime_state.py`，read_result_status 在 `cleaning/result.py`），不放入 state 模块

#### Scenario: 未来扩展约束
- **WHEN** 未来在 state 模块中添加通用状态存储
- **THEN** 该存储 SHALL 被至少两个不同领域模块使用，否则应留在使用方领域模块内部
