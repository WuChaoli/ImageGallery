## ADDED Requirements

### Requirement: Vector 验证边界具有直接测试证据
VectorField 验证集门禁 SHALL 由确定性测试直接覆盖完整性、顺序、维度、有限数值和比较容差，任一失败均不得写入目标向量。

#### Scenario: 验证输出乱序
- **WHEN** 调用方提供数量正确但 probe 顺序不符合冻结验证集的输出
- **THEN** 整批向量写入失败且已有向量保持不变

#### Scenario: 比较容差边界
- **WHEN** 验证输出分别落在冻结容差以内和以外
- **THEN** 容差内输出通过，容差外输出使整批写入失败

#### Scenario: 非有限验证值
- **WHEN** 验证输出或目标向量包含 NaN、正 Inf 或负 Inf
- **THEN** 系统拒绝整批写入且不发布任何新值

### Requirement: 组合提交并发冲突具有直接测试证据
Data+Vector 组合提交 SHALL 由测试证明在目标 Branch 基线过期时既不推进 Dataset，也不发布 pending 或 current vectors。

#### Scenario: 组合提交使用过期基线
- **WHEN** 组合提交携带的 DatasetView 已不再是目标 Branch Head
- **THEN** 操作返回稳定冲突，Dataset 和全部 VectorField 的可见状态均保持不变
