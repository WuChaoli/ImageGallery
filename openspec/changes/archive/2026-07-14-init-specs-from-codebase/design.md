## Context

ImageGallery 已完成首版核心开发，包含 storage、dataset、schemas、importers、cleaning、operators、visualization、annotations 等 8 个领域模块。代码已通过单元测试和集成测试验证，但 OpenSpec 中没有任何 spec 文件记录这些已实现的能力契约。本次变更从现有代码库逆向提取规格，建立 spec-driven 基线。

## Goals / Non-Goals

**Goals:**
- 从现有源码逆向提取 13 个能力域的 spec 文件（9 个已实现 + 4 个空模块占位）
- 每个 spec 包含可测试的 requirement 和 scenario
- 覆盖所有用户可见的公开 API 和关键内部契约
- 为后续变更提供 spec-driven 参照基线

**Non-Goals:**
- 不修改任何现有代码
- 不补充新功能或新模块
- 不对现有实现做架构重构建议
- 不描述未来演进路线（非目标已在架构文档中覆盖）

## Decisions

### 1. Spec 粒度：按领域模块而非文件级别

**选择**：每个 spec 对应一个领域模块（storage-system、dataset-management 等），而非每个源文件一个 spec。

**理由**：用户交互以模块为单位（如 `Storage`、`Dataset`、`BasicCleaner`），按领域组织 spec 与用户心智模型一致。文件级粒度会导致 spec 碎片化，难以维护。

**替代方案**：按源文件粒度（如 storage-base、storage-filesystem、storage-minio 各一个 spec）——拒绝，因为过度碎片化且同一能力跨多文件。

### 2. Spec 内容：描述行为契约而非实现细节

**选择**：spec 描述"系统应该做什么"（接口、输入输出、错误条件），不描述"怎么做"（具体算法、内部数据结构）。

**理由**：OpenSpec spec 是契约层，实现细节属于 design 和代码。保持 spec 稳定，不受实现重构影响。

### 3. 场景格式：WHEN/THEN 可测试场景

**选择**：每个 requirement 至少一个 WHEN/THEN scenario，直接对应可验证的测试用例。

**理由**：spec 场景应可直接映射为测试，确保规格与实现一致。现有测试已覆盖大部分场景，spec 是对测试意图的文档化。

### 4. 能力域划分

| Spec 名称 | 对应源码目录 | 关键公开 API |
|---|---|---|
| storage-system | storage/ | Storage, FileSystemStorage, MinioStorage |
| dataset-management | dataset/ | Dataset, DatasetExporter, DatasetLoader |
| image-import | importers/, schemas/ | ImportPipeline, SourceParser, RawDatasetSchema |
| cleaning-runtime | cleaning/runtime.py, execution.py, state.py, runtime_state.py, graph.py | CleaningRuntime, CleanerExecution, CleanerResult, CleaningStateGraph |
| cleaning-operators | operators/ | OperatorSpec, ConfiguredOperatorSpec, OperatorRegistry, create_default_registry |
| cleaning-config | cleaning/toml_config.py, selection.py, config.py | CleanerConfig, select_operators, build_cleaner_toml_template |
| cleaning-preview | cleaning/preview.py, html_preview.py, preview_policy.py, policy.py | build_preview, apply_final_action, write_preview_html, PreviewPolicy |
| visualization | visualization/ | show_image_grid, render_image_grid |
| annotations | annotations/ | LabelImgExporter, LabelImgLoader, read_pascal_voc_xml, write_pascal_voc_xml |
| utils | utils/ | （空命名空间占位） |
| reports | reports/ | （空命名空间占位） |
| config-namespace | config/ | （空命名空间占位） |
| state-namespace | state/ | （空命名空间占位；清洗状态实现在 cleaning/） |

## Risks / Trade-offs

- **[Spec 与实现漂移]** → 后续代码变更时需同步更新 spec；OpenSpec 的 change 工作流可强制约束
- **[规格不完整]** → 首版可能遗漏边缘场景；后续变更中逐步补齐
- **[内部契约暴露]** → 部分场景涉及内部实现（如 ParameterComputer），需权衡公开程度；选择描述接口契约而非内部逻辑
- **[空模块占位]** → utils/reports/config/state 当前为空命名空间，spec 只记录职责边界和扩展约束，无行为可测试；后续有实质实现时需补充 scenario
