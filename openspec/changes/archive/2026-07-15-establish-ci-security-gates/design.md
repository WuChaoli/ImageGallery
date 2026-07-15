## Context

仓库已经通过 `make lint` 和 `make test` 提供本地质量检查，但 GitHub 尚未配置工作流和受保护分支，安全结果仍依赖开发者主动执行。仓库是 Python 3.10 的 local-first package，使用 `uv.lock` 管理可复现依赖；CI 需要覆盖普通代码、第三方依赖、Git 历史、工作流定义和最终 Python 包五类攻击面。

设计采用“快速 PR 门槛、深度 PR 门槛、定时巡检、发布验证”四层结构。PR 层只阻断高确定性问题；定时层负责发现规则或漏洞库更新后暴露的存量风险；发布层验证真正交付的 wheel，而不是工作区源码。

## Goals / Non-Goals

**Goals:**

- 所有进入默认分支的 PR 必须通过不可绕过的质量与高危安全检查。
- CI 命令与本地命令尽量共用入口，使失败可在开发机复现。
- 新增密钥、任何已知依赖漏洞和 High/Critical 代码风险零容忍，同时为存量与误报提供有审计信息的限时豁免。
- 限制 GitHub Actions 权限和第三方 Action 漂移，保护 CI 自身。
- 发布物必须可安装、带 SBOM，并能追溯到仓库、commit 和构建工作流。

**Non-Goals:**

- 第一阶段不阻断代码扫描的 Medium/Low 告警；依赖漏洞不按严重性放行。
- 不引入商业安全平台、自托管 runner 或自动部署生产环境。
- 不把安全扫描当成渗透测试、恶意依赖检测或人工安全审查的替代品。
- 不修改 ImageGallery 公共 API、数据契约或运行时行为。

## Decisions

### 1. 使用 GitHub 原生能力为主、Python 专用工具补齐

GitHub Actions 负责执行和展示结果，CodeQL 负责跨文件代码数据流分析，Dependabot 负责持续依赖监控；Gitleaks 补充提交级密钥扫描，`pip-audit` 补充可在本地复现的 Python 漏洞检查，`zizmor` 检查 Actions 工作流本身。相比全部采用第三方扫描平台，这一组合维护成本和凭证暴露面更小；相比只运行 `make check`，它覆盖了依赖、密钥、供应链和 CI 配置风险。

CodeQL 是否可作为 required check 取决于仓库可见性和 GitHub 套餐。若私有仓库未启用 GitHub Code Security，第一阶段以 `zizmor + pip-audit + Gitleaks` 保持其余门槛有效，并把 CodeQL 标记为待仓库能力开启后启用，而不是用一个永远不运行的 required check 锁死合并。

### 2. 工作流按职责拆分，并为 required checks 使用稳定唯一的 job 名称

- `ci.yml`：Ruff、Pyright、pytest、wheel 构建与安装 smoke test。
- `security.yml`：Gitleaks、`pip-audit`、`zizmor`；只对本次 PR 引入的问题执行阻断。
- CodeQL 使用 GitHub 默认配置或独立高级配置，不与普通 CI 耦合。
- `scheduled-security.yml`：按周执行完整历史密钥、完整依赖和主分支扫描。
- `release.yml`：在发布触发时重新构建、安装验证、生成 SBOM 和 artifact attestation。

拆分允许任务并行、失败责任清晰，也避免一个可选的平台能力导致所有基础检查无法运行。required job 名称必须跨工作流唯一且保持稳定，防止分支保护引用歧义。

### 3. 采用风险分级和“只阻断新增问题”策略

PR 必须阻断：lint/type error、测试失败、构建/安装失败、新增疑似真实密钥、任何已知依赖漏洞、CodeQL 新增 High/Critical 告警，以及 `zizmor` 的高可信危险工作流问题。依赖漏洞采用全量阻断，是因为 `pip-audit` 不提供稳定的严重性过滤；代码扫描的 Medium/Low 首阶段只报告。

存量问题先扫描、确认和建立窄粒度基线。任何豁免必须记录工具规则或漏洞编号、适用路径、理由、负责人和到期日期；禁止通过宽泛路径或禁用整类规则来追求绿灯。该策略避免第一次启用扫描时被历史噪音锁死，同时保证风险不会继续增长。

### 4. 默认最小化 Actions 权限和外部执行面

工作流顶层默认使用 `permissions: contents: read`，仅在具体 job 确有需要时授予更小范围的写权限。PR 检查不向来自 fork 的不可信代码提供 secrets，不使用可让不可信 PR 以目标分支权限执行代码的危险组合。第三方 Action 固定到完整 commit SHA，并由 Dependabot 维护版本更新。

### 5. 锁文件是依赖扫描与安装的权威输入

CI 使用已提交的 `uv.lock` 进行 frozen sync，依赖声明与锁文件不一致即失败。`pip-audit` 扫描由锁文件解析出的实际环境，避免只看宽泛的 `pyproject.toml` 下限。Dependabot 负责提出依赖和 Actions 更新 PR，但所有自动 PR 仍必须通过相同 required checks。

### 6. 发布检查真正的构建产物

发布工作流从干净 checkout 构建 wheel 和 sdist，在新的隔离环境中只安装 wheel 并执行 import/核心 smoke test。验证通过后生成 CycloneDX SBOM，并使用 GitHub artifact attestation 记录产物摘要、commit 和工作流来源。任一步失败都不创建正式发布产物。

### 7. GitHub ruleset 构成最终强制边界

默认分支禁止直接推送和 force push，要求通过 PR、解决 review conversation，并要求稳定的 CI 与安全 job 成功。管理员是否允许 bypass 必须显式配置；推荐不允许日常 bypass，仅保留受审计的紧急恢复路径。仅创建 YAML 而不配置 required checks 不视为完成。

## Risks / Trade-offs

- [首次扫描存在存量问题或误报] → 上线前先观察扫描结果，建立具体且有到期时间的基线，只对新增风险启用阻断。
- [CodeQL 在私有仓库不可用] → 在实施前检查仓库能力；不把不可运行的检查设为 required，保留其他门槛并记录启用条件。
- [依赖漏洞全量阻断可能增加升级压力] → 对确认不可利用的漏洞允许限时例外，但要求书面影响分析和到期复查。
- [第三方 Action 或扫描器自身被攻击] → 固定完整 SHA、最小权限、避免向 PR 暴露 secrets，并让 Dependabot 提出升级。
- [CI 时间增长] → lint、test、security、build 并行；PR 只扫描变更，完整扫描移到每周。
- [required job 改名导致合并锁死] → 将 job 名称视为稳定接口，修改工作流时同步审查 ruleset。
- [SBOM 或 attestation 被误解为安全证明] → 文档明确它们只提供组件清单和来源可追溯性，不证明代码无漏洞。

## Migration Plan

1. 在不设置 required checks 的情况下加入工作流，以只读权限运行首轮基线扫描。
2. 修复或登记存量密钥、依赖漏洞和 High/Critical 代码发现，确认每个 job 在普通 PR 和 fork PR 场景都能正确结束。
3. 先将 lint、test、build、Gitleaks、依赖审计和 workflow audit 设置为 required checks。
4. 仓库能力允许且 CodeQL 基线稳定后，再把 CodeQL High/Critical 结果纳入 required checks。
5. 开启 Dependabot、安全定时巡检和发布证明；最后禁止默认分支直接推送与 force push。

回滚时可以临时从 ruleset 移除发生平台故障的具体 required check，但不得删除扫描配置或宽泛关闭所有分支保护；恢复后应补跑该 commit 的对应检查并记录原因。

## Open Questions

- 实施时需确认 GitHub 仓库是 public 还是 private，以及当前套餐是否支持私有仓库 CodeQL、secret scanning 和 artifact attestation。
- 实施时需确认默认分支实际名称；当前文档使用 `main` 表示，工作流和 ruleset 必须以远端仓库设置为准。
