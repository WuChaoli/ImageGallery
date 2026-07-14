## Why

仓库目前依赖开发者手动执行 lint、类型检查和测试，尚未由 GitHub 在合并入口统一强制执行，也缺少密钥、已知依赖漏洞、代码数据流和 CI 工作流本身的安全检查。需要把已建立的本地质量检查升级为可审计、不可绕过的 CI 安全门槛，避免有风险的变更进入主分支或发布产物。

## What Changes

- 建立 GitHub Actions PR 检查，强制执行 Ruff、Pyright、pytest、Python 包构建和干净环境安装验证。
- 为 PR 增加新增密钥、任何已知依赖漏洞、CodeQL 高危代码问题和 GitHub Actions 工作流风险检查。
- 建立定时全仓扫描，持续发现新披露的依赖漏洞、历史密钥和主分支代码风险。
- 为发布产物生成 SBOM 与来源证明，并在产物构建或验证失败时阻止发布。
- 通过 GitHub ruleset 或分支保护把稳定的 PR 检查配置为 required checks，并限制直接推送、强制推送和未完成审查的合并。
- 建立安全发现基线与限时豁免机制：存量问题可经记录后暂不阻断，但不允许新增同等级问题；豁免必须包含理由、负责人和到期时间。

## Capabilities

### New Capabilities

- `ci-security-gates`: 定义 PR、定时巡检和发布阶段的自动安全检查、阻断等级、分支保护及豁免治理。

### Modified Capabilities

- `lint-pipeline`: 将既有本地 lint 入口纳入 GitHub Actions required check，并明确 CI 中的失败语义。

## Impact

- 新增 `.github/workflows/`、Dependabot 配置以及安全扫描工具配置。
- 调整 `Makefile` 和开发依赖，使关键检查可在本地与 CI 使用同一入口复现。
- 影响 GitHub 仓库的 Actions、Code Security、ruleset/branch protection 和发布设置。
- 不改变 `image_gallery` 的公共 Python API 或数据集行为。
