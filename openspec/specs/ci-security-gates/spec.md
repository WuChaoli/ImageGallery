## Purpose

定义 Pull Request、默认分支、定时扫描和发布阶段的自动安全门槛，以及分支保护与安全豁免治理。
## Requirements
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

### Requirement: 新增密钥必须阻断 PR

系统 SHALL 扫描 Pull Request 新增的代码和提交内容中的密码、API Key、Token、私钥及其他凭证模式。发现未被具体且有理由豁免的疑似真实密钥 MUST 阻止合并。

#### Scenario: PR 引入 API Key
- **WHEN** Pull Request 新增内容包含被密钥扫描器识别的 API Key
- **THEN** 密钥检查失败，输出脱敏后的定位信息并阻止合并

#### Scenario: 测试夹具触发已批准豁免
- **WHEN** 测试夹具命中特定规则且存在限定到具体发现、包含理由和到期时间的有效豁免
- **THEN** 密钥检查不因该具体发现失败，同时继续扫描其他内容

### Requirement: 已知依赖漏洞必须阻断 PR

系统 SHALL 基于提交的锁文件审计实际安装的 Python 依赖。任何已知漏洞 MUST 阻止合并，除非存在包含漏洞编号、影响分析、负责人和到期时间的有效例外。

#### Scenario: 锁文件包含已知漏洞
- **WHEN** PR 的锁定依赖版本命中任意未豁免的已知漏洞
- **THEN** 依赖审计失败并提示受影响包、漏洞编号和可用修复版本

#### Scenario: 已知漏洞存在有效例外
- **WHEN** 依赖审计发现的漏洞存在限定到具体漏洞、包含影响分析、负责人和到期时间的有效例外
- **THEN** CI 记录该例外并继续审计其他依赖

### Requirement: 高危代码安全发现必须阻断 PR

系统 SHALL 对 Python 代码执行支持跨文件数据流分析的安全扫描。PR 新增的 Critical 或 High 代码安全发现 MUST 阻止合并；仓库能力不支持该扫描时 MUST 明确报告未启用原因，且不得把不可运行的检查配置为 required check。

#### Scenario: 新增高危数据流漏洞
- **WHEN** 安全扫描确认 PR 新增的外部输入可未经校验流入危险操作并被评为 High
- **THEN** 代码安全检查失败并阻止合并

#### Scenario: 仓库不具备 CodeQL 能力
- **WHEN** 当前 GitHub 套餐未向仓库提供 CodeQL
- **THEN** 实施记录该限制，其他安全门槛继续生效且 CodeQL 不被配置为 required check

### Requirement: GitHub Actions 工作流必须自我防护

所有工作流 SHALL 默认使用只读仓库权限，第三方 Action MUST 固定到完整 commit SHA，并 SHALL 扫描危险事件、表达式注入、过度权限和向不可信 PR 暴露 secrets 的配置。高可信危险发现 MUST 阻止合并。

#### Scenario: 工作流申请全局写权限
- **WHEN** PR 将工作流配置为 `permissions: write-all`
- **THEN** 工作流安全检查失败并阻止合并

#### Scenario: 普通 PR 工作流运行
- **WHEN** PR 检查无需写入仓库或读取部署凭证
- **THEN** 工作流仅获得完成检查所需的只读权限且不注入仓库 secrets

### Requirement: 安全扫描必须持续覆盖主分支

系统 SHALL 按固定计划对默认分支执行完整依赖漏洞、Git 历史密钥和代码安全扫描。定时扫描发现风险 MUST 产生可追踪结果，即使该风险不是由当天的 PR 引入。

#### Scenario: 新漏洞影响既有依赖
- **WHEN** 已合并依赖在之后被披露存在 High 或 Critical 漏洞
- **THEN** 下一次定时扫描或依赖监控产生安全告警并提供升级入口

#### Scenario: 新规则识别历史密钥
- **WHEN** 密钥扫描规则更新后识别出 Git 历史中的旧凭证
- **THEN** 完整历史扫描失败并提示必须轮换凭证和评估历史清理

### Requirement: 发布产物必须可验证且可追溯

正式发布 SHALL 从干净 checkout 构建 wheel 和 sdist，在隔离环境验证 wheel 安装及核心 smoke test，并为通过验证的产物生成 SBOM 和来源证明。任一步失败 MUST 阻止正式发布。

#### Scenario: 发布验证成功
- **WHEN** wheel 和 sdist 构建成功、wheel 隔离安装及 smoke test 通过且 SBOM 与来源证明生成成功
- **THEN** 工作流允许发布这些经过验证的产物

#### Scenario: SBOM 生成失败
- **WHEN** Python 包本身构建成功但 SBOM 或来源证明生成失败
- **THEN** 发布工作流失败且不得发布不完整的正式产物

### Requirement: 默认分支必须启用合并保护

GitHub 默认分支 SHALL 要求通过 Pull Request 和配置的 required checks 后才能合并，并 MUST 禁止日常直接推送、force push 和删除。检查名称 MUST 唯一且稳定。

#### Scenario: required check 失败
- **WHEN** PR 的任一 required check 失败或尚未完成
- **THEN** GitHub 不允许该 PR 合并到默认分支

#### Scenario: 尝试直接推送默认分支
- **WHEN** 普通维护者尝试绕过 PR 直接推送默认分支
- **THEN** GitHub ruleset 或分支保护拒绝该推送

### Requirement: 安全豁免必须可审计并自动到期

安全扫描豁免 MUST 限定到具体规则、漏洞或发现，并记录理由、负责人和到期日期。已过期或宽泛禁用整个扫描类别的豁免 MUST 被视为无效。

#### Scenario: 豁免已经过期
- **WHEN** 被安全扫描命中的发现仅存在已过期豁免
- **THEN** 扫描按未豁免发现处理并根据严重性阻止合并

#### Scenario: 申请宽泛目录豁免
- **WHEN** 配置试图跳过整个源码目录或禁用全部密钥、依赖或代码扫描规则
- **THEN** 豁免治理检查失败或代码审查拒绝该配置

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
