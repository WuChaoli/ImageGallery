## MODIFIED Requirements

### Requirement: 受管输出路径安全约束
系统 SHALL 在 Storage 写入操作时强制执行路径安全约束。

#### Scenario: 拒绝路径逃逸
- **WHEN** 写入路径包含 `..` 或符号链接导致逃逸出受管根目录
- **THEN** 拒绝写入并抛出 PathSecurityError

#### Scenario: 拒绝跨 storage 写入
- **WHEN** 算子或任务尝试绕过平台直接写入非受管路径
- **THEN** 拒绝写入并抛出 PathSecurityError

#### Scenario: 正式产物禁止覆盖
- **WHEN** 写入目标路径已存在正式产物且 overwrite 未显式设为 True
- **THEN** 拒绝写入并抛出 FileExistsError

#### Scenario: 临时产物隔离
- **WHEN** 写入临时产物
- **THEN** 临时文件写入 run 目录的 tmp 子目录，正式产物通过原子提交写入

#### Scenario: 原子提交语义
- **WHEN** 正式产物提交
- **THEN** 先写入临时文件，校验完整性，写 manifest，再原子移动到正式位置
