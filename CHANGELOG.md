# Changelog

本文档记录本项目的重要变更。

格式参考 Keep a Changelog，版本号遵循 Semantic Versioning。

## [Unreleased]

### Added

- 新增的功能

### Changed

- 已有功能的变更

### Deprecated

- 即将废弃的功能

### Removed

- 已移除的功能

### Fixed

- Bug 修复

### Security

- 安全相关修复

## [0.0.1] - 2026-07-10

### Added

- 初始化仓库基线、项目质量检查配置和本地开发忽略规则。
- 新增 Storage 基础能力，支持直接连接、批量读写和导入图片路径分片。
- 新增 Dataset 文件基础、原始数据集 Schema 契约、标签校验和图片元数据扩展。
- 新增本地目录、数据集文件和 URL 列表导入边界，补齐基础导入元数据提取与原始数据集导入流水线。
- 新增数据集图片读取能力，并支持通过 Dataset 读取后端存储中的图片。
- 新增算子注册表、内置算子规格和基础 Cleaner 核心能力。
- 新增清洗关系结果持久化、派生尺寸算子、图片质量计算器、质量逻辑算子和精确重复图片算子。
- 新增 Notebook 路径、存储、数据集和清洗配置 helper，并加入 sample 1000 清洗验证 Notebook。
- 新增清洗参数执行计划编译、参数调度器、算子求值器和 Cleaner 计划执行能力。
- 新增感知哈希计算器、感知重复图片分组和感知重复算子注册。
- 新增清洗结果预览查询、HTML 渲染和 Cleaner HTML 预览 API。
- 新增语义重复图片算子能力，包括 embedding provider 边界、embedding 产物写入、语义分组和算子注册。
- 新增轻量质量算子能力，包括质量细节、边框填充和格式细节参数计算器。
- 新增 Cleaner Runtime 公共契约、配置、算子选择、状态图编译、运行状态、运行产物和事件执行能力。
- 新增 Dataset 加载/导出插件边界、LabelImg Pascal VOC 辅助函数、LabelImg 导出和标注回载能力。
- 新增 Cleaner 结果导出、结果预览、断点恢复和重新运行能力。
- 新增 Stage 1 到 Stage 4、导入、算子、清洗平台、Notebook、Cleaner Runtime、LabelImg、语义重复和轻量质量算子的设计文档与开发计划。
- 新增 MinIO 导入、算子、清洗、感知重复、语义重复、轻量质量和 Cleaner Runtime 相关 Notebook/集成验证入口。

### Changed

- 重构清洗平台，转向 Cleaning V3 的算子、参数计算和结果关系模型。
- 将后端图片读取统一收敛到 Dataset 读取路径。
- 复用 Notebook helper 简化清洗集成测试和验证流程。
- 为参数计算器增加执行模式，并重构 Cleaner 的计划编译与执行流程。
- 迁移 Dataset IO 到统一的 load/export 模型。
- 将 Cleaner 重构为更明确的执行生命周期。
- 优化 Cleaner 预览 HTML 布局和感知重复默认阈值。
- 统一 Dataset 路径加载接口。
- 归档历史设计文档，并补充中文注释与 Notebook 说明。
- 整理主分支本地工作区改动和 Cleaner Runtime StateGraph 收尾改动。

### Deprecated

- 暂无。

### Removed

- 暂无。

### Fixed

- 修复 Stage 1 quickstart 与原始标签契约不一致的问题。
- 修复 Stage 1 基础能力评审中发现的缺口。
- 修复参数计算器依赖扩展问题。
- 修复感知重复分组类型收尾问题。
- 修复语义 embedding provider 的导入检查和类型标注问题。
- 修复算子配置未传递到参数计算器的问题。
- 修复语义 embedding manifest 不完整和批量推理问题。
- 修复 Cleaner Runtime policy merge、preview 默认值、TOML policy 缺失和 mypy narrowing 问题。
- 修复 Runtime 参数节点 policy 投影、graph adapter 调用、事件 `run_id` 转换和状态生命周期问题。
- 修复运行产物路径、manifest 持久化和断点恢复产物校验问题。
- 修复重试耗尽后 Runtime fake stage 状态未标记失败的问题。
- 修复 Cleaner 结果导出、算子预览过滤、缓存路径隐藏和预览 policy 生效问题。
- 修复感知重复 Notebook 的结果生命周期、执行变量和关系导出问题。
- 修复 Cleaner 结果导出与 manifest 校验完整性问题。
- 修复 Dataset 路径构造接口缺失问题。

### Security

- 暂无。

### Commit 明细（2026-07-10 之前）

#### 2026-07-09

- `e5103e4` 修复结果导出和 manifest 校验完整性。
- `1afd2a3` 通过结果导出感知哈希关系。
- `f6376cd` 修复感知哈希 Notebook 执行变量。
- `8496c96` 修复感知哈希 Notebook 结果生命周期。
- `1aaee78` 验证 Cleaner Runtime 迁移。
- `6123950` 清理 Cleaner Runtime Notebook 输出。
- `75c5d2f` 新增 Cleaner Runtime Notebook 示例。
- `f9b610e` 将恢复产物哈希锚定到图。
- `d7d8e56` 修复 Cleaner 恢复产物校验。
- `3bfffd4` 支持 Cleaner 恢复和重新运行。
- `c0e2469` 修复 Cleaner 结果预览 policy 生效问题。
- `6727d31` 隐藏 Cleaner 结果缓存路径。
- `f26a042` 修复 Cleaner 结果导出和算子预览过滤。
- `3ccfba2` 新增 Cleaner 结果导出和预览。
- `7ad3b8b` 修复 Runtime fake stage 在重试耗尽后的失败状态。
- `12014f3` 将 Dataset IO 迁移到 load/export。
- `cde353f` 修复 Cleaner Runtime 状态生命周期。
- `32a4cb7` 支持将 LabelImg 标注加载回数据集。
- `3c3bd89` 支持为 LabelImg 导出数据集。
- `bfd23e3` 新增 LabelImg Pascal VOC helper。
- `a6b8873` 新增可插拔数据集加载导出。
- `477bc6b` 将 Cleaner 重构为执行生命周期。
- `880f365` 新增 LabelImg 数据集 IO 实现计划。
- `37b18e6` 修复 Runtime 事件 `run_id` 状态存储转换。
- `d885851` 新增 LabelImg 数据集 IO 设计。
- `c1a9dcb` 修复 Runtime graph adapter 调用和测试。
- `05c49f0` 新增 Cleaner Runtime 事件执行。
- `bc98274` 加固产物路径和 manifest 持久化。
- `1fba97c` 新增 Cleaner Runtime 状态和产物。
- `118563d` 修复参数节点 policy 投影与 Runtime policy 对齐问题。
- `8f51611` 编译 Cleaner StateGraph。
- `f517050` 修复 TOML policy 缺失和 mypy 类型收窄问题。
- `e5dbc49` 新增 Cleaner 配置和算子选择。
- `bb50564` 修复 Cleaner Runtime policy merge 和预览默认值。
- `5b6b441` 新增 Cleaner Runtime 公共契约。
- `f657955` 新增 Cleaner Runtime StateGraph 实现计划。
- `888b7f0` 归档历史文档。
- `50c0303` 扩展 Cleaner Runtime 验证策略。
- `6da6a0b` 细化 Cleaner Runtime policy。
- `24895e5` 新增 Cleaner Runtime 用户友好输入说明。
- `949f7d2` 新增 Cleaner Runtime StateGraph 设计。

#### 2026-07-08

- `c7ded44` 合并 `feat/parameter-computer-config` 分支。
- `4aa0635` 调整感知重复默认阈值。
- `5a251b6` 优化清洗预览 HTML 布局。
- `88e0935` 合并 `feat/light-quality-operators` 分支。
- `9961fc1` 生成逐算子的轻量质量预览。
- `79a96f3` 合并 `feat/semantic-duplicate-operator` 分支。
- `125fba8` 覆盖轻量质量算子集成测试。
- `400b7f6` 注册轻量质量算子。
- `cd55499` 修复语义 embedding 批量推理。
- `216b685` 新增格式细节参数计算器。
- `dd52c19` 新增边框填充参数计算器。
- `d76440b` 新增质量细节参数计算器。
- `909ec73` 验证语义重复清洗运行。
- `1d32dd1` 注册语义重复算子。
- `7472450` 新增语义重复 embedding 分组。
- `f7fcf1e` 新增轻量质量算子实现计划。
- `e0cc870` 修复语义 embedding manifest 完整性。
- `7f08fe1` 写入语义 embedding 产物。
- `c8e22d7` 修复算子配置传递到参数计算器的问题。
- `c6633dc` 格式化语义 provider 测试。
- `010c819` 修复语义 provider 导入检查和类型标注。
- `6fb55a8` 新增语义 embedding provider 边界。
- `d13a9f4` 新增语义重复算子实现计划。
- `9a74d8f` 新增轻量质量算子批次设计。
- `32fb407` 合并 `feat/cleaning-result-preview` 分支。
- `548e26e` 指定语义重复默认模型。
- `653b243` 补充感知重复 Notebook 配置。
- `e1f4b7f` 以 HTML 预览感知哈希重复结果。
- `4d122c2` 新增语义重复算子设计。
- `e708ca4` 新增 Cleaner HTML 预览 API。
- `6f2e46b` 渲染清洗预览 HTML。
- `d550375` 新增清洗预览查询 helper。
- `6f517e5` 新增清洗结果预览计划。
- `8dad8af` 新增清洗结果预览设计。
- `f653160` 添加注释。
- `1a9fd5a` 导出 clean 和 dropped 感知哈希表。
- `efcbf15` 将 Notebook 数据集路径移动到 datasets 目录。
- `47117a8` 在感知哈希 Notebook 中使用 helper 数据集。
- `aaec792` 为感知哈希 Notebook 添加中文注释。
- `5c58012` 新增感知哈希重复算子 Notebook。
- `10a980a` 修复感知重复分组类型收尾问题。
- `407ddef` 覆盖感知重复 Cleaner 运行测试。
- `f5948b3` 注册感知重复算子。
- `4ebddc1` 新增感知重复分组。
- `9b103af` 新增感知哈希计算器。
- `a3bb898` 新增感知哈希重复算子计划。
- `1250266` 新增感知哈希重复算子设计。
- `1aa9f65` 重构文档。
- `58b88d7` 新增清洗计划器和调度器 Notebook 冒烟验证。
- `ea2ff76` 新增清洗 Notebook 冒烟验证设计。
- `74f878d` 验证清洗计划器和调度器重构。
- `b9f07b3` 重构基础 Cleaner 的计划编译和执行。
- `d4f23f9` 新增算子求值器。
- `a9368c5` 新增参数调度器。
- `3fd0f78` 编译清洗参数执行计划。
- `7dd093d` 忽略虚拟环境符号链接。
- `bb60443` 为参数计算器新增执行模式。
- `ba4f8cf` 忽略项目 worktree。
- `3c8130d` 细化清洗重构计划评审。
- `9284ecf` 新增清洗计划器和调度器重构计划。
- `59b15ab` 预留清洗 checkpoint 扩展。
- `813e9f7` 新增清洗计划器和调度器重构设计。

#### 2026-07-07

- `ad44edc` 验证 Notebook helper 验证流程。
- `8c7c2be` 新增 Cleaning V3 sample 1000 Notebook。
- `21ff845` 重构清洗集成测试以复用 Notebook helper。
- `faee972` 新增 Notebook 数据集和配置 helper。
- `20108f6` 新增 Notebook 路径和存储 helper。
- `f20057b` 新增 Notebook helper 包导入测试。
- `f69bf47` 新增 Cleaning V3 sample 1000 Notebook 设计。

#### 2026-07-06

- `4a570a7` 验证 Cleaning V3 第一批算子。
- `3a0cf1e` 修复参数计算器依赖扩展问题。
- `225112f` 新增精确重复算子。
- `1845017` 新增质量逻辑算子。
- `36ab6e2` 新增图片质量计算器。
- `ef25dca` 新增派生尺寸算子。
- `32f4a08` 持久化清洗关系输出。
- `e01c592` 新增 Cleaning V3 第一批算子计划。
- `d0d5724` 新增 Cleaning V3 第一批算子设计。
- `42f18a3` 录入测试集。
- `2202d2d` 新增默认 MinIO 数据集构建设计。
- `75c1b13` 彻底重构清洗平台。

#### 2026-07-03

- `b65c9e4` 合并 `feat/stage4-cleaning-operators` 分支。
- `af9c564` 新增 Cleaning Platform V3 设计。
- `fef540e` 新增 Stage 4 Cleaner 快速开始文档。
- `58e0df2` 新增算子验证 Notebook。
- `bcd1fbd` 新增算子 Notebook 验证计划。
- `4ea5b4d` 新增基础 Cleaner 核心。
- `facc026` 新增算子注册表和内置规格。
- `44ffce3` 对齐算子 Notebook 与 Dataset 图片读取能力。
- `92fe067` 覆盖 Cleaner 远程数据集图片测试。
- `dc35305` 重构为通过 Dataset 读取后端图片。
- `178203e` 新增数据集图片读取能力。
- `c1c77af` 新增数据集图片读取计划。
- `318c6a6` 新增数据集图片读取设计。
- `f14ad63` 新增算子验证 Notebook。
- `f2f1ca1` 补充 MinIO 算子 Notebook 验证说明。
- `33e92a2` 新增算子 Notebook 验证设计。
- `ab01542` 更新文档。
- `351ace6` 优化 importer 类输入。
- `096f9d4` 提交空变更占位。
- `2ea74fe` 允许数据集解析器选择图片列。
- `6bb0998` 补充导入流水线源解析器 API 说明。

#### 2026-07-02

- `61b7fef` 新增 MinIO 导入 Notebook 验证计划。
- `bc51815` 新增 MinIO 导入 Notebook。
- `05d35f3` 补充 MinIO 导入 Notebook 验证说明。
- `51fcd83` 新增路径加载测试。
- `2ad5a28` 扩展原始图片元数据。
- `7748fc1` 补充原始元数据扩展设计说明。
- `e1a12fe` 支持导入图片路径分片。
- `4306e22` 补充导入路径分片设计说明。
- `288a285` 补齐项目质量检查。
- `46554f0` 新增 Stage 2 本地导入示例文档。
- `76cf01e` 新增 URL 列表导入边界。
- `abcb76b` 新增原始数据集导入流水线。
- `9987083` 新增基础导入元数据提取器。
- `c47d2e1` 新增数据集文件源读取器。
- `03f0fa1` 新增本地目录源读取器。
- `cf89963` 修复 Stage 1 quickstart 与原始标签契约不一致的问题。
- `ffc21fb` 新增 MinIO Notebook dotenv 配置。
- `9c04edf` 忽略本地 MinIO Notebook。
- `7bd7f41` 对齐导入架构和 Stage 2 计划。
- `6fccfae` 新增原始数据集标签校验。
- `b743915` 支持批量存储读写重载。
- `5cc039f` 新增直接存储连接能力。
- `5788fc6` 新增数据集绘制支持。
- `a22cedc` 修复 Stage 1 基础能力评审缺口。
- `b240376` 新增 Stage 1 快速开始示例文档。
- `fc87102` 新增原始数据集 Schema 契约。
- `c2097c0` 新增 Dataset 文件基础能力。
- `abfc838` 新增 Storage 基础能力。
- `b7e1d7c` 忽略本地 agent 产物。
- `0ea937c` 初始化仓库基线。
