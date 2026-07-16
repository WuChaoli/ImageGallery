## Context

仓库已经以 Ruff、Pyright、pytest、Gitleaks、pip-audit、zizmor、Dependabot、包 smoke test、SBOM 和 artifact attestation 建立第一阶段门槛。当前缺口不是扫描器数量，而是 Python 代码安全与测试质量的覆盖深度：Ruff 仅启用基础规则，CodeQL 尚未配置，CI 不衡量变更覆盖率，包验证和 SBOM 也未完全对齐实际交付物。

只读基线扫描证明整组启用规则不可行：候选规则产生 1725 条发现，其中 973 条是 pytest 合法 `assert`，306 条是低收益 `TRY003`，218 条是与中文标点规范冲突的 `RUF002/RUF003`。设计因此继续采用 balanced 门禁：高确定性问题阻断 PR，高成本或高误报检查进入定时报告。

## Goals / Non-Goals

**Goals:**

- 用精选规则覆盖安全模式、异常语义、pytest 风格、代码简化和明显复杂度增长。
- 让新增或修改代码提供足够测试证据，同时不让历史覆盖率欠债锁死无关 PR。
- 用 CodeQL 补充 Ruff 无法完成的跨文件数据流分析。
- 规范 suppression、文档、依赖、Python 版本和发布包验证。
- 保持普通 PR 快速、确定、可在本地复现。

**Non-Goals:**

- 不启用 Ruff `ALL`，不禁止 `for` 循环，不要求循环改为推导式。
- 不引入 Black、isort、Semgrep、Nox 或 Tox。
- 不把 Pyright warning、Vulture、mutation testing、随机顺序或外部链接检查设为普通 PR 硬门禁。
- 不设置函数行数、文件行数或字节级可复现构建门槛。
- 不在未获用户选择时为项目指定许可证类型。

## Decisions

### 1. Ruff 采用白名单式精选规则

在现有规则上增加 `S`、`BLE001`、`TRY004`、`PT`、`C901`、`C4`、`SIM102`、`SIM103`、`SIM114`、`SIM115` 和 `RET504`。复杂度阈值设为 15。测试目录只对 pytest 和确定性假数据固有模式豁免 `S101/S105/S106/S108`；`S506`、`S603` 等必须逐行验证。

不启用 `TRY003`、`RUF002/RUF003`、`SIM108`、`RET501`、`ANN` 或会以消除循环为目标的规则。`BLE001` 只允许在批处理、插件、IO adapter 和调度隔离边界具体行豁免，并要求异常被转换、记录、重抛或写入结构化失败结果。

### 2. Pyright 保持 error 阻断、warning 可见

strict 模式和当前 error 级别保持不变。warning 不建立数量基线，避免 pandas stubs 和第三方类型更新造成无关阻断。所有 `type: ignore` 与 `pyright: ignore` 必须指定具体规则；动态数据可在解析边界使用 `Any`，进入核心领域逻辑前必须校验或窄化。

### 3. 覆盖率采用全仓底线与 diff coverage 双门槛

实施时先用默认快速测试测量稳定基线，全仓阈值取稳定值向下取整，只防止明显回退；PR 对新增或修改的可执行行要求 80% diff coverage。没有可执行 Python 变更时检查成功。`slow` 与 `real_dataset` 不进入普通 PR coverage，继续显式运行。

### 4. CodeQL advanced setup 与 Ruff 分层

Ruff `S` 负责单文件快速模式；独立 CodeQL workflow 分析 Python 和 GitHub Actions 的跨文件数据流。新增 High/Critical 发现阻断，Medium/Low 报告。暂不引入 Semgrep，只有形成带正反例测试的项目特定规则后才独立评估。

### 5. 默认测试与深度质量巡检分层

PR 执行 pytest strict markers/config、默认快速测试和覆盖率。定时任务执行随机顺序并保留 seed、对 `stability` marker 重复 5 次、Vulture 高置信度报告、外部链接和第三方 warning 汇总。核心纯逻辑 mutation testing 作为手动或低频报告，不阻断 PR。

### 6. 文档检查只阻断确定性问题

Markdown 检查标题、列表、围栏、文件尾换行、重复锚点和链接语法，不强制行宽、表格重排或中文标点。内部链接和高确定性英文拼写阻断；外部 HTTP 链接只定时报告。OpenSpec strict validation 和 frozen lockfile 继续作为权威一致性检查。

### 7. 包检查对齐支持声明和实际产物

CI 显式安装 Python 3.10，作为最低支持版本执行完整检查；最新稳定 Python 执行快速测试和包安装。支持版本以 CI 矩阵为准。package 检查验证 wheel 与 sdist、元数据、内容、sdist 重建、隔离安装和关键模块导入。

发布 SBOM 从安装目标 wheel 的隔离环境生成，而不是从开发环境生成。正式对外发布前必须存在用户确认的 LICENSE 和一致的包元数据；依赖许可证先报告，形成允许/禁止策略后再考虑阻断。

## Risks / Trade-offs

- [规则整改改变错误契约] → `TRY004` 实施前搜索调用者并用测试固定正确异常类型。
- [安全规则误报测试夹具] → 只豁免四类已确认测试模式，其余发现逐行审查。
- [覆盖率数字驱动低价值测试] → 同时要求边界/错误场景，覆盖率只作为最低证据。
- [CodeQL 平台检查与风险判定混淆] → workflow 成功和 code scanning merge protection 分开配置，保持稳定 check 名称。
- [定时任务噪声无人处理] → 每类报告保留可复现 seed、路径或置信度，并限制到可行动范围。
- [最新 Python 版本引发第三方暂时不兼容] → 最低版本完整检查为核心门槛，最新稳定版本失败需明确分类，不通过静默排除依赖解决。
- [许可证未知阻塞发布] → 仅正式发布前阻断，具体许可证必须由用户选择。

## Migration Plan

1. 固化候选规则基线和契约测试，修复产品代码 `assert`、外部 XML、异常类型、宽泛异常和复杂度存量问题。
2. 启用精选 Ruff、pytest strict 配置和 suppression 治理。
3. 测量覆盖率并建立全仓底线与 80% diff coverage。
4. 配置 CodeQL advanced setup，并在观察现有发现后启用 High/Critical merge protection。
5. 增加文档、OpenSpec、锁文件和包检查。
6. 显式配置最低与最新稳定 Python 验证，修正发布 SBOM。
7. 增加定时随机、稳定性、Vulture、链接、warning 和低频 mutation 报告。
8. 本地完整验证后通过真实 PR 确认 required checks，再收敛文档并归档。

回滚仅允许移除发生平台故障的具体 required check；不得宽泛关闭 Ruff 安全、类型、依赖或分支保护。恢复后必须补跑相同 commit。

## Open Questions

- 项目正式许可证类型由用户在首次正式对外发布前另行确认。
- “最新稳定 Python”的具体版本在实施时依据官方稳定版本确定并写入 workflow，不使用浮动的 runner 默认 Python。
