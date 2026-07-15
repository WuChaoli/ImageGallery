## 1. 仓库能力与安全基线

- [x] 1.1 确认 GitHub 默认分支、仓库可见性、套餐以及 CodeQL、secret scanning、artifact attestation 和 ruleset 的可用范围，并记录不可用能力的替代路径
- [x] 1.2 在不阻断合并的模式下运行 Ruff、Pyright、pytest、Gitleaks、pip-audit 和 workflow audit 首轮扫描，分类记录真实问题、误报和存量基线
- [x] 1.3 定义安全豁免文件或治理格式，要求包含具体规则或漏洞编号、影响范围、理由、负责人和到期日期，并增加过期检查

## 2. 可复现的本地安全入口

- [x] 2.1 在开发依赖和锁文件中加入构建、依赖审计、SBOM 与工作流审计所需的固定工具，并验证 `uv sync --frozen` 可复现安装
- [x] 2.2 为 lint、测试、依赖审计、workflow audit、包构建和 wheel smoke test 提供可在本地与 CI 共用的 Makefile 入口
- [x] 2.3 为安全入口添加自动化测试或固定的失败夹具，证明新增密钥、高危依赖、危险 workflow 和不可安装 wheel 会产生非零退出码

## 3. PR 质量工作流

- [x] 3.1 新增最小只读权限的 `ci.yml`，在 Pull Request 和默认分支 push 上并行运行 Ruff/Pyright 与 pytest
- [x] 3.2 在干净环境按锁文件安装依赖，启用缓存但禁止依赖未提交状态或开发者本地环境
- [x] 3.3 构建 wheel 与 sdist，在新的隔离环境仅安装 wheel 并执行 package import 和核心 smoke test
- [x] 3.4 使用本地 workflow lint 或解析测试验证 `ci.yml` 的触发条件、唯一 job 名称、权限和失败传播

## 4. PR 安全工作流

- [x] 4.1 新增 Gitleaks PR 增量扫描，固定第三方 Action 或工具版本、脱敏输出，并验证新增密钥会阻断
- [x] 4.2 新增基于锁定环境的 pip-audit 检查，实现任何未豁免已知漏洞均阻断
- [x] 4.3 新增 zizmor GitHub Actions 审计，阻断表达式注入、过度权限、不可信 PR secrets 暴露和未批准的可变 Action 引用
- [x] 4.4 为所有工作流设置顶层 `contents: read` 最小权限，对确需写权限的 job 单独授权并固定第三方 Action 到完整 commit SHA
- [x] 4.5 在仓库能力允许时启用 CodeQL Python 扫描，完成基线治理后验证新增 High/Critical 发现可阻断 PR；不可用时记录启用条件且不创建悬空 required check

## 5. 持续依赖与定时巡检

- [x] 5.1 配置 Dependabot 维护 Python 依赖和 GitHub Actions 引用，使自动升级 PR 经过相同 required checks
- [x] 5.2 新增每周定时安全工作流，对默认分支执行完整 Git 历史密钥、完整锁定依赖和适用的代码安全扫描
- [x] 5.3 配置安全报告的保留与可追踪输出，验证定时任务失败会产生可见告警而不会静默结束

## 6. 发布供应链门槛

- [x] 6.1 新增最小权限的发布工作流，从干净 checkout 重新构建并重复 wheel 隔离安装与 smoke test
- [x] 6.2 为通过验证的发布产物生成 CycloneDX SBOM，并验证 SBOM 能对应锁定依赖和发布产物
- [x] 6.3 为发布产物生成 GitHub artifact attestation；若仓库能力不支持，则记录限制并在支持前禁止宣称产物已具备来源证明
- [x] 6.4 验证构建、安装、smoke test、SBOM 或 attestation 任一失败都不会创建正式发布

## 7. GitHub 合并保护

- [x] 7.1 在工作流稳定运行后创建默认分支 ruleset 或 branch protection，要求 PR、review conversation resolution 和唯一稳定的质量/安全 required checks
- [x] 7.2 禁止普通维护者直接推送、force push 和删除默认分支，并配置受审计的紧急恢复路径而非日常 bypass
- [x] 7.3 用一个成功 PR 和分别触发 lint、test、secret、dependency、workflow 与 build 失败的验证 PR，确认 GitHub 实际拒绝合并

## 8. 文档与完成验证

- [x] 8.1 更新 README 或开发文档，解释各工作流、失败排查、本地复现、安全告警和限时豁免流程
- [x] 8.2 运行 `make check`、全部安全入口、workflow lint、OpenSpec validate 和发布 dry run，记录真实通过结果
- [x] 8.3 检查 required check 名称与 GitHub ruleset 完全一致、无悬空检查，并确认所有 OpenSpec tasks 完成后再进入文档同步与归档流程
