## MODIFIED Requirements

### Requirement: PR 质量检查必须由 GitHub 强制执行

系统 SHALL 在每个面向默认分支的 Pull Request 上通过跨平台 Python CI 入口执行 Ruff 格式检查、lint、类型检查、默认快速测试、Python 包构建和隔离安装验证。GitHub Actions MUST NOT 依赖 GNU Make。任一检查失败或未完成 MUST 阻止合并，现有 required job 名称 MUST 保持稳定。

#### Scenario: PR 质量检查全部通过
- **WHEN** Pull Request 中的代码通过格式、lint、类型、测试、构建和隔离安装验证
- **THEN** 所有质量 required checks 成功，PR 可以继续满足其他合并条件

#### Scenario: Python 文件未格式化
- **WHEN** Pull Request 包含 Ruff formatter 判定为需要修改的 Python 文件
- **THEN** 名为 `lint` 的 required check 失败且 checkout 不被 CI 自动修改

#### Scenario: 构建产物无法安装
- **WHEN** 源码测试通过但生成的 wheel 在干净环境中无法安装或导入
- **THEN** 构建检查失败并阻止 PR 合并

#### Scenario: GitHub runner 未安装 GNU Make
- **WHEN** GitHub Actions runner 执行质量或安全检查
- **THEN** 工作流直接调用 Python CI 入口并能够完成检查，不因缺少 Make 而失败
