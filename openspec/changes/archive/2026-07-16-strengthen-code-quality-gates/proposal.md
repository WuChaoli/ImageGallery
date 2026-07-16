## Why

仓库已有 Ruff、Pyright、pytest 和基础供应链安全门槛，但当前 lint 规则覆盖有限，尚未治理变更覆盖率、跨文件代码安全、复杂度、测试有效性、文档一致性和发布物级 SBOM。需要在保持快速默认测试和低误报的前提下，将高确定性问题转化为可执行门禁，并把高成本或高噪声检查放入定时巡检。

## What Changes

- 精选启用 Ruff 安全、异常语义、pytest 风格、代码简化和复杂度规则；明确不禁止 `for` 循环，不整组启用高噪声规则。
- 规范 Pyright suppression 与 `Any` 使用边界，继续阻断 error 但不因现有 warning 阻断。
- 建立全仓覆盖率基线防回退与 PR diff coverage 80% 门槛。
- 启用 CodeQL advanced setup 承担 Python 与 GitHub Actions 跨文件数据流分析，Ruff `S` 保持本地快速反馈，暂不引入 Semgrep。
- 增加 pytest 严格配置，并将随机顺序、稳定性重复、死代码、mutation testing 等高成本检查分流到定时或手动任务。
- 增加 Markdown、内部链接、英文拼写、OpenSpec、锁文件和 suppression 治理检查。
- 显式验证最低 Python 3.10 与最新稳定 Python，增强 wheel/sdist 内容、元数据、隔离安装和 smoke test。
- 修正发布 SBOM，使其描述实际 wheel 的隔离运行环境；正式发布前要求明确项目许可证和对应元数据。

## Capabilities

### New Capabilities

- `code-quality-gates`: 定义精选 Ruff 规则、复杂度上限、Pyright suppression 和代码豁免治理。
- `test-quality-gates`: 定义 pytest 风格、覆盖率、随机/重复测试、mutation testing 和默认/定时分层。
- `documentation-quality-gates`: 定义 Markdown、内部/外部链接、英文拼写和 OpenSpec 文档校验边界。
- `package-quality-gates`: 定义 Python 版本兼容、包内容与元数据验证、发布物 SBOM 和许可证门槛。

### Modified Capabilities

- `lint-pipeline`: 扩充 lint 权威入口必须执行的精选 Ruff 与 Pyright 治理要求。
- `ci-security-gates`: 增加 CodeQL advanced setup、覆盖率 required checks、Python 兼容验证和增强发布门槛。

## Impact

- 修改 `pyproject.toml`、uv 锁文件、CI/security/release workflows 和仓库级质量检查工具。
- 增加覆盖率、diff coverage、CodeQL、文档检查、包检查及定时质量巡检配置。
- 需要修复启用规则前确认的少量存量发现，包括产品代码 `assert`、外部 XML 解析、异常类型、宽泛异常边界和复杂度超限。
- 不修改 ImageGallery 产品功能或公共 API 目标行为；异常类型修正可能影响错误契约，实施时必须先搜索调用者并用测试证明。
