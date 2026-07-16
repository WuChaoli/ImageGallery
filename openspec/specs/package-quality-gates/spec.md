# package-quality-gates Specification

## Purpose
TBD - created by archiving change strengthen-code-quality-gates. Update Purpose after archive.
## Requirements
### Requirement: CI 必须显式验证支持的 Python 版本

CI SHALL 显式安装 Python 3.10 并执行完整质量、测试和包验证，且 SHALL 在实施时确定的最新稳定 Python 上执行默认快速测试与包安装。支持版本 MUST 以 CI 矩阵为准，不得依赖 runner 默认 Python。

#### Scenario: runner 默认 Python 变化
- **WHEN** `ubuntu-latest` 更新预装 Python
- **THEN** CI 继续使用 workflow 显式声明的受支持版本

#### Scenario: 最新稳定 Python 不兼容
- **WHEN** 默认快速测试或 wheel 安装在最新稳定 Python 上失败
- **THEN** 兼容检查失败并明确区分项目问题与第三方依赖暂时不兼容

### Requirement: 包检查必须验证 wheel 与 sdist

package required check SHALL 构建 wheel 与 sdist，校验元数据和内容，从 sdist 重建 wheel，并在隔离环境安装目标 wheel 后导入顶层包与关键公开模块。构建产物 MUST NOT 包含 tests、Notebook、缓存、`.env`、本地数据或内部 CI 脚本。

#### Scenario: sdist 缺少构建文件
- **WHEN** 从生成的 sdist 无法重新构建 wheel
- **THEN** package check 失败并阻止合并

#### Scenario: wheel 包含本地环境文件
- **WHEN** wheel 内容包含 `.env`、缓存或本地数据
- **THEN** package check 失败并报告违规路径

### Requirement: 发布 SBOM 必须对应实际 wheel

正式发布 SHALL 在干净隔离环境安装经过 smoke test 的目标 wheel，并从该环境生成 CycloneDX SBOM。开发环境依赖清单 MUST NOT 作为发布物 SBOM。

#### Scenario: SBOM 包含未交付开发工具
- **WHEN** 发布 SBOM 仅因构建环境存在而包含 Ruff、Pyright 或 pytest
- **THEN** 发布验证失败并要求从目标 wheel 的隔离环境重新生成

### Requirement: 正式发布前必须明确许可证

首次正式对外发布前，仓库 MUST 包含用户确认的 LICENSE，包元数据 MUST 与其一致。系统 SHALL 先报告依赖许可证，且在没有已批准允许/禁止策略时 MUST NOT 擅自按许可证类型阻断普通 PR。

#### Scenario: 未选择项目许可证
- **WHEN** 正式发布工作流运行但仓库没有用户确认的 LICENSE 或一致元数据
- **THEN** 发布失败且不得自动选择许可证

#### Scenario: 普通 PR 更新依赖
- **WHEN** 依赖许可证报告发现尚未纳入正式策略的许可证
- **THEN** CI 报告该信息但不因未定义策略阻断普通 PR
