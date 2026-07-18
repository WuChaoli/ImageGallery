## ADDED Requirements

### Requirement: ParameterComputer 配置解析一致性
系统 SHALL 在计划编译、状态图编译与 dry-run 诊断中使用一致的 ParameterComputer 依赖闭包、配置投影、hash 与冲突检测规则。

#### Scenario: 深层依赖配置投影
- **WHEN** 逻辑算子依赖的参数由具有上游依赖的 ParameterComputer 产生
- **THEN** 计划、状态图与 dry-run 均把声明的配置键投影到依赖闭包中的对应 computer

#### Scenario: 空配置 hash
- **WHEN** ParameterComputer 未声明或未收到相关配置键
- **THEN** 计划与状态图继续使用 `default` 作为配置 hash

#### Scenario: 共享 computer 配置冲突
- **WHEN** 两个逻辑算子向同一 ParameterComputer 投影出不同配置
- **THEN** 计划、状态图与 dry-run 均抛出相同的配置冲突错误

#### Scenario: 重构后顺序与状态语义不变
- **WHEN** 使用相同算子、registry 与运行策略编译和执行清洗
- **THEN** 参数计划、图节点顺序、plan hash、持久化 schema、失败恢复、hook 与产物语义保持不变
