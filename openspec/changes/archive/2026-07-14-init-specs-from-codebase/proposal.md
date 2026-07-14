## Why

ImageGallery 已完成首版核心开发，涵盖存储、数据集、导入、清洗运行时、算子、预览和可视化等模块，但 OpenSpec 中还没有任何 spec 文件来记录这些已实现的能力契约。需要从现有代码库逆向提取规格，建立 spec-driven 基线，为后续变更提供可追溯的参照。

## What Changes

- 新增 storage-system spec，描述统一存储抽象（文件系统 + MinIO）、image_uri 生成、批量读写和对象生命周期管理契约
- 新增 dataset-management spec，描述 Dataset 读写、preview/scan/export、fingerprint 和图片 bytes 批量读取契约
- 新增 image-import spec，描述 ImportPipeline 导入流程、SourceParser 来源扩展、元数据抽取、raw Dataset schema 和导入报告产物
- 新增 cleaning-runtime spec，描述 CleaningStateGraph 编译、CleaningRuntime 执行、运行状态存储、resume 和 CleanerResult 导出
- 新增 cleaning-operators spec，描述 OperatorSpec/ConfiguredOperatorSpec 规格模型、OperatorRegistry 注册机制、ParameterComputer 参数计算单元和内置算子目录
- 新增 cleaning-config spec，描述 TOML 配置格式、CleanerConfig 构建、算子选择器和配置哈希
- 新增 cleaning-preview spec，描述 preview_merge/apply_merge 归并策略、final_action 计算、HTML 预览和算子级 PreviewPolicy
- 新增 visualization spec，描述 Notebook 图片网格渲染和可视化辅助能力
- 新增 annotations spec，描述 LabelImg 标注格式 IO 能力
- 新增 utils spec，描述跨模块工具命名空间占位
- 新增 reports spec，描述报告命名空间占位
- 新增 config-namespace spec，描述配置命名空间占位
- 新增 state-namespace spec，描述运行状态命名空间占位

## Capabilities

### New Capabilities
- `storage-system`: 统一存储抽象层——Storage ABC 接口、FilesystemStorage、MinIOStorage、image_uri 生成、批量读写和对象生命周期管理
- `dataset-management`: Dataset 文件读写（Parquet/CSV/JSONL）、preview、scan、export、fingerprint、图片 bytes 批量读取和 DatasetImage 枚举
- `image-import`: ImportPipeline 导入闭环——SourceParser 扩展点（本地目录/URL列表/数据集文件）、基础元数据抽取、RawDatasetSchema 契约、raw.parquet/failure_manifest/import_report 产物
- `cleaning-runtime`: 清洗运行时生命周期——CleaningStateGraph 编译、CleaningRuntime 执行、SQLite/JSON 状态存储、resume 断点恢复、CleanerResult 导出和 debug bundle
- `cleaning-operators`: 算子模型——OperatorSpec/ConfiguredOperatorSpec 规格与配置、OperatorRegistry 注册、ParameterComputer 参数计算单元、内置算子目录（format/size/quality/content/metadata/duplicate）
- `cleaning-config`: 清洗配置——TOML 配置格式、CleanerConfig 构建、算子选择器（select_operators）、配置哈希和模板导出
- `cleaning-preview`: 清洗预览与归并——PreviewResult 构建、apply_final_action 归并、HTML 预览生成、PreviewPolicy 算子级预览策略
- `visualization`: 可视化——Notebook 图片网格渲染（show_image_grid）和缩略图辅助
- `annotations`: 标注 IO——LabelImg XML 格式读写
- `utils`: 跨模块工具命名空间——当前为空占位，约束未来只放置被多模块共享的小工具
- `reports`: 报告命名空间——当前为空占位，约束未来只保存报告摘要和报告文件
- `config-namespace`: 配置命名空间——当前为空占位，约束未来只存放跨模块共享配置常量
- `state-namespace`: 运行状态命名空间——当前为空占位，清洗运行状态实现在 cleaning 模块内

### Modified Capabilities
<!-- 无现有 spec，全部为新增 -->

## Impact

- 新增 13 个 spec 文件到 `openspec/specs/` 目录（9 个已实现能力 + 4 个空模块占位）
- 不涉及任何代码变更，纯文档规格提取
- 为后续变更提供 spec-driven 基线参照
- 影响范围：所有现有模块的契约文档化
