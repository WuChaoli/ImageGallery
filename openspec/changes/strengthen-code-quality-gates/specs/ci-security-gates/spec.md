## ADDED Requirements

### Requirement: CodeQL advanced setup 必须扫描跨文件风险

系统 SHALL 使用独立 CodeQL advanced workflow 扫描 Python 与 GitHub Actions，并 SHALL 覆盖面向 `master` 的 PR、默认分支 push 和定时全量扫描。新增 High 或 Critical 发现 MUST 阻止合并，Medium、Low 与 Note SHALL 报告。

#### Scenario: 外部输入流入危险操作
- **WHEN** CodeQL 确认 PR 新增外部输入未经验证跨文件流入危险操作并评为 High
- **THEN** code scanning merge protection 阻止合并

#### Scenario: CodeQL workflow 成功但存在 Medium
- **WHEN** 分析成功并产生新增 Medium 发现
- **THEN** 发现保持可见但不因本阶段阈值直接阻断 PR

### Requirement: PR 必须执行双层覆盖率门槛

系统 SHALL 将默认快速测试的全仓覆盖率基线和 80% diff coverage 配置为 PR required check。覆盖率检查 MUST 不依赖 slow、real dataset 或外部 SaaS。

#### Scenario: diff coverage 不足
- **WHEN** PR 修改的可执行行覆盖率低于 80%
- **THEN** required check 失败并阻止合并

### Requirement: 质量门禁必须显式选择 Python 版本

CI SHALL 在 Python 3.10 执行完整检查，并 SHALL 在最新稳定 Python 执行快速兼容检查。workflow MUST NOT 依赖 runner 默认 Python 版本。

#### Scenario: 最低版本完整检查失败
- **WHEN** Python 3.10 的 lint、测试或包验证失败
- **THEN** 对应 required check 失败

### Requirement: 定时质量巡检不得扩大普通 PR 成本

随机顺序、稳定性重复、Vulture、外部链接、第三方 warning、全支持版本矩阵和 mutation testing SHALL 在定时或手动 workflow 中执行，且 MUST NOT 成为普通 PR required check，除非后续独立 OpenSpec change 明确批准。

#### Scenario: mutation score 较低
- **WHEN** 低频 mutation testing 发现存活 mutation
- **THEN** 任务产生可追踪报告但不阻断无关普通 PR

### Requirement: 发布验证必须绑定包、SBOM 和许可证

正式发布 SHALL 验证 wheel 与 sdist、从 sdist 重建、隔离安装和关键导入，并 SHALL 为目标 wheel 的隔离运行环境生成 SBOM 和来源证明。首次正式对外发布还 MUST 具有用户确认的 LICENSE 与一致包元数据。

#### Scenario: 开发环境 SBOM 被用于发布
- **WHEN** SBOM 包含仅存在于开发环境且未随 wheel 交付的工具
- **THEN** 发布验证失败

#### Scenario: 正式发布缺少许可证
- **WHEN** 发布工作流未找到用户确认的 LICENSE 或一致元数据
- **THEN** 发布失败且不得生成正式发布物
