## MODIFIED Requirements

### Requirement: 核心不变量
系统 SHALL 在所有清洗运行时流程中维护以下核心不变量。

#### Scenario: image_uri 唯一引用
- **WHEN** 图片被导入到平台后
- **THEN** image_uri 是该图片在系统中的唯一主引用地址，所有后续操作（清洗、可视化、导出）均通过 image_uri 访问图片

#### Scenario: source_uri 仅用于追溯
- **WHEN** 导出 clean/dropped/full 数据集供外部消费
- **THEN** source_uri 默认不包含在导出数据集中，仅在审计和追溯场景中可用

#### Scenario: raw Dataset 不可变
- **WHEN** 清洗运行时执行算子评估和归并
- **THEN** 原始 raw Dataset 文件不被修改，clean/dropped/full 是独立的导出视图

#### Scenario: clean + dropped = full
- **WHEN** 清洗归并完成
- **THEN** clean 数据集与 dropped 数据集的并集等于 full 数据集（按 image_id 集合验证）

#### Scenario: 归并只能由 MergePolicy 生成
- **WHEN** 生成 clean、dropped、full 数据集
- **THEN** 必须通过 MergePolicy 基于逻辑算子的评估结果生成，不能由物理执行直接产出

#### Scenario: 算子按能力命名
- **WHEN** 面向用户展示或配置逻辑算子
- **THEN** 使用能力优先命名（如 blur、dimension、exact_duplicate），不暴露底层工具名称（OpenCV、fastdup、DINOv2）

#### Scenario: 单张图片失败不中断批次
- **WHEN** 某张图片在导入或清洗过程中失败
- **THEN** 该图片记录在 failure_manifest 中，其余图片继续处理
