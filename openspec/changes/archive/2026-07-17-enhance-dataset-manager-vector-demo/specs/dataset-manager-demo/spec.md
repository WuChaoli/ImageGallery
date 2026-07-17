## MODIFIED Requirements

### Requirement: 单 Notebook 演示完整 Dataset 生命周期
系统 SHALL 在一个中文 Notebook 中使用选定的真实 Backend 连续演示 DatasetManager 的主要用户旅程。

#### Scenario: 从导入到版本分叉
- **WHEN** 用户从头执行 Notebook 的业务章节
- **THEN** 系统创建 Repo、Dataset、Tag，托管导入 20 张图片并提交 V1，读取行和图片，再创建 Checkpoint 与 experiment Branch 并分别推进 main 和 experiment

#### Scenario: 模型托管的向量生成
- **WHEN** 用户执行向量生命周期章节
- **THEN** Notebook 展示冻结 Model 定义和强绑定 VectorField，默认对 main Head 生成向量，以 DataFrame 同时读取普通列与向量列，并演示重复调用跳过、覆盖生成和指定 View 范围
- **AND** Notebook 验证向量生成不会创建或移动 Iceberg Snapshot，并解释 Repo 当前向量按 asset_id 复用的语义

#### Scenario: 回退与 Clone
- **WHEN** 用户继续执行高级生命周期章节
- **THEN** 系统演示固定 View、Branch 回退和从固定 View Clone

#### Scenario: 关闭并重新连接
- **WHEN** Notebook 关闭第一组 Manager 和 Storage 客户端后以同一配置重建客户端
- **THEN** Repo、Dataset、Refs、Clone、图片、Tag、冻结模型定义、VectorField 和已生成向量均可重新打开并保持持久状态

### Requirement: Notebook 可重复且可自动验证
Notebook MUST 不依赖隐藏的 kernel 状态，并 SHALL 提供自动化验证覆盖材料、环境选择、安全边界和真实 Backend 从头执行。

#### Scenario: 从干净 kernel 执行 managed 路径
- **WHEN** 自动化测试在隔离目录以 managed demo Backend 从第一单元执行到最后一单元
- **THEN** 所有单元成功，模型注册、向量生成、跳过、覆盖、指定 View、Snapshot 不变和重连恢复断言通过，输出不包含凭证且测试结束无遗留 demo 容器或客户端进程

#### Scenario: 检查中文教学内容
- **WHEN** 检查 Notebook 和 README 的用户说明
- **THEN** 环境配置、每个生命周期阶段、模型托管向量语义、错误恢复和清理步骤均有中文解释，代码实体名称保持英文
