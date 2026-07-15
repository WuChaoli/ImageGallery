## MODIFIED Requirements

### Requirement: RunStore 存储模式
系统 SHALL 提供 RunStore 抽象，支持 memory、temporary、disk 三种运行存储模式。

#### Scenario: memory 模式
- **WHEN** storage="memory"
- **THEN** 表和 JSON 数据保存在进程内存中，无文件系统持久化

#### Scenario: temporary 模式（默认）
- **WHEN** storage="temporary" 或未指定
- **THEN** 使用临时目录，cleanup() 时删除

#### Scenario: disk 模式
- **WHEN** storage="disk"
- **THEN** 使用 `cache_root / run_id` 路径，支持长期保存和 resume

#### Scenario: memory 模式下语义算子报错
- **WHEN** storage="memory" 且配置了 semantic_duplicate 算子
- **THEN** before_run_check 阶段报错，提示使用 temporary 或 disk 模式

#### Scenario: RunStore 协议
- **WHEN** 检查 RunStore 接口
- **THEN** 包含 write_table、read_table、write_json、read_json、materialize_dataset、cleanup 方法
