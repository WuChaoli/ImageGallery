## 1. 前置与基线

- [x] 1.1 确认 `standardize-python-ci-entrypoint` 已完成或本分支可复用其 Python CI 入口，避免同时维护两套命令实现
- [x] 1.2 用只读命令记录精选 Ruff、Pyright warning、pytest、覆盖率、包内容和现有 CodeQL 状态基线
- [x] 1.3 为 Ruff 规则白名单、禁止规则、suppression 和 CI 配置编写失败优先的契约测试

## 2. Ruff 安全与异常规则

- [x] 2.1 修复产品代码 `S101`，用显式运行时校验替代会被优化移除的 `assert` 并补回归测试
- [x] 2.2 验证 LabelImg 外部 XML 攻击面，使用安全解析方案修复 `S314` 并补恶意/异常 XML 测试
- [x] 2.3 审查现有 `BLE001`，窄化普通业务异常并为合理隔离边界补结构化处理和具体理由
- [x] 2.4 修复 `TRY004` 异常类型，先搜索调用者并用测试固定 TypeError 与 ValueError 契约
- [x] 2.5 启用 `S` 与 `BLE001/TRY004`，仅为 tests 配置 `S101/S105/S106/S108` 目录豁免并逐行处理其他发现

## 3. 风格、pytest 与复杂度

- [x] 3.1 启用 `PT`、`C4`、`SIM102/103/114/115`、`RET504`，修复存量且验证不会禁止 `for` 循环
- [x] 3.2 启用 pytest strict markers/config，修复 `PT011/PT017` 并使用稳定异常语义断言
- [x] 3.3 将 `C901` 阈值设为 15，重构或理由充分地窄豁免现有复杂度 16 函数
- [x] 3.4 添加治理测试，禁止 `TRY003`、`RUF002/RUF003`、`SIM108`、`RET501` 和 Ruff `ANN` 被意外纳入

## 4. Pyright 与 suppression 治理

- [x] 4.1 实现并测试具体规则 suppression 检查，拒绝宽泛 `noqa`、`type: ignore`、`pyright: ignore` 和文件级关闭
- [x] 4.2 审查现有 suppression，保留第三方 stub 必需的最小规则并修复项目自身可消除的问题
- [x] 4.3 为 Pyright strict error 等级编写配置契约测试，保持 warning 可见但不阻断
- [x] 4.4 记录 `Any` 的动态边界规范并用现有公共 API 类型检查验证核心领域接口未被 Any 污染

## 5. 覆盖率门禁

- [x] 5.1 添加 coverage 与 diff coverage 工具，通过默认快速测试测量可重复的 `src/image_gallery` 基线
- [x] 5.2 将全仓阈值设为稳定基线向下取整值，并配置 PR diff coverage 80%
- [x] 5.3 为无可执行 Python 变更、低 diff coverage、全仓回退和禁止整模块排除编写契约测试
- [x] 5.4 将覆盖率加入 Python CI 与 GitHub required check，继续排除 slow 和 real_dataset

## 6. CodeQL advanced setup

- [x] 6.1 添加扫描 Python 与 GitHub Actions 的独立 CodeQL advanced workflow，覆盖 PR、master push 和定时执行
- [x] 6.2 固定 CodeQL Actions 完整 SHA、最小化权限并通过 zizmor 与 workflow 契约测试
- [x] 6.3 运行首轮 CodeQL 基线并逐项审查发现，不建立宽泛路径忽略
- [x] 6.4 在 GitHub 配置新增 High/Critical code scanning merge protection，并验证 Medium 以下只报告

## 7. 文档与仓库治理

- [x] 7.1 配置精选 Markdown 结构规则，验证不强制行宽、表格重排、代码块语言或中文标点转换
- [x] 7.2 增加仓库内部链接硬检查和外部 HTTP 链接定时报告
- [x] 7.3 配置英文高确定性拼写检查与项目词典，排除中文自然语言语法审查
- [x] 7.4 将 `openspec validate --strict`、frozen uv sync 和 suppression 治理接入统一检查且补契约测试

## 8. Python 版本与包验证

- [x] 8.1 在 workflows 中显式安装 Python 3.10，并在实施时确认的最新稳定 Python 上运行快速兼容检查
- [x] 8.2 增强 package 检查以验证 wheel/sdist、元数据、禁止内容、sdist 重建、隔离安装和关键模块导入
- [x] 8.3 为包内容和 Python 版本矩阵编写契约测试，确认不依赖 runner 默认 Python
- [x] 8.4 从安装目标 wheel 的隔离环境生成发布 SBOM，验证不包含仅存在于开发环境的工具
- [x] 8.5 在发布检查中要求用户确认的 LICENSE 与一致元数据，但不擅自选择许可证或按未定义策略阻断依赖许可证

## 9. 定时与手动深度质量检查

- [x] 9.1 增加保留 seed 的 pytest 随机顺序定时任务，并验证失败可复现
- [x] 9.2 注册 `stability` marker 并在定时任务中重复 5 次，仅标记并发、状态、缓存和资源生命周期高风险测试
- [x] 9.3 增加 Vulture 高置信度、第三方 warning、外部链接和全支持 Python 版本报告，不自动删除代码
- [x] 9.4 为核心纯逻辑模块建立低频 mutation testing 报告，排除 IO、Notebook、第三方 adapter 和真实数据测试
- [x] 9.5 验证所有深度检查均未被配置为普通 PR required check

## 10. 验证与 GitHub 强制

- [x] 10.1 在 Windows 通过 Python CI 入口运行格式、精选 lint、Pyright、默认测试、覆盖率、安全和包验证
- [x] 10.2 运行 slow/real-data 显式验收及定时任务的可执行 smoke test，记录无法在本地复现的平台边界
- [x] 10.3 运行 workflow、包、suppression 和 OpenSpec 契约测试及 `openspec validate --strict`
- [x] 10.4 通过真实 PR 验证 required checks、CodeQL High/Critical 保护、最低/最新 Python 与覆盖率行为
- [x] 10.5 同步 AGENTS.md 与 README，明确硬门禁、定时报告、豁免规则和许可证待用户选择边界
