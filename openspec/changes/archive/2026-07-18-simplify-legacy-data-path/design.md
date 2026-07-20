## Context

旧平台的数据流为 SourceParser → ImportPipeline → Storage/RawDatasetSchema → Dataset，并通过 LabelImg Loader/Exporter 与 Pascal VOC 目录互操作。当前实现行为测试较完整，但 `ImportPipeline.run()` 同时负责单项导入、异常翻译和产物落盘，`annotations/labelimg.py` 同时负责目录编排、表格值规范化、坐标转换和 XML 读写，Dataset 的格式分派也直接放在领域对象中。重构必须在 Python 3.10 下保持公开签名与异常/返回语义，且不能将旧平台与 DatasetManager 类型或持久化模型混合。

## Goals / Non-Goals

**Goals:**

- 用私有、领域内聚的函数和模块分离表格 I/O、单记录导入、导入产物写出、Pascal VOC XML 和 LabelImg 表格规范化职责。
- 缩短主要编排函数并消除 Storage 批量操作的重复异常隔离代码。
- 通过 characterization tests 固定公开 API、`image_uri`/`source_uri`、失败清单、LabelImg round-trip 和 XML 安全解析语义。
- 默认测试全部通过，源代码覆盖率不低于 90%，diff coverage 不低于 80%。

**Non-Goals:**

- 不新增数据格式、导入模式、服务端 API、Web UI 或报告能力。
- 不修改 `__all__`、公开函数/类/方法签名、返回类型或异常类型/消息。
- 不修改 RawDatasetSchema 字段、LabelImg 目录协议、bbox 坐标协议和 DatasetManager 新平台。
- 不为了“统一”而建立跨旧平台和新平台的宽泛抽象。

## Decisions

### 1. 私有模块按领域职责拆分，而非建立通用框架

Dataset 使用私有表格 I/O 模块封装格式判定和 pandas 读写；LabelImg 使用私有 Pascal VOC 模块与表格值模块；ImportPipeline 使用同模块内私有数据结构/函数表达单记录结果与产物写出。这样可以缩短公共实现文件，同时避免一次性抽象只被一个模块使用的“通用转换层”。备选方案是建立跨模块 I/O registry，但当前仅三种固定表格格式且没有扩展需求，复杂度收益不成立。

### 2. 公共路径由重新导入保持稳定

`image_gallery.annotations.labelimg` 继续提供现有 helper 名称，`image_gallery.annotations` 继续只导出 Loader/Exporter。私有实现可以移动，但所有已存在的调用路径和 `inspect.signature` 结果必须不变。备选方案是保留包装函数；直接从私有模块重新导入可以减少重复转发代码，同时保持调用语义。

### 3. ImportPipeline 保持顺序执行和失败隔离

主循环只负责按顺序调用单记录导入并累计成功/失败；单记录函数仍在同一 `try/except` 边界内完成 metadata、Storage 写入和 raw row 构造。失败项继续记录原始 source、失败阶段、异常类名、消息和时间。不会引入并发、重试或事务，因为这些会改变顺序、时间或副作用语义。

### 4. Storage 复用一个私有逐项执行器

批量写、读、存在性检查和删除都通过同一个私有迭代器把单项异常转换为 `StorageBatchResult`。具体操作仍调用原有公开/私有方法，保持输入顺序、catch-all 隔离和错误字符串。不会改变公开批量 API，也不会让单对象 API吞掉异常。

## Risks / Trade-offs

- [Risk] 私有模块拆分可能造成循环导入 → 仅在协议类型位置使用前向引用/局部导入，并运行完整 import/test 门禁。
- [Risk] 直接重导入 helper 会意外改变签名或路径 → 运行公共 API signature contract 与现有直接导入测试。
- [Risk] Pipeline 拆分可能改变失败阶段或时间字段 → characterization tests 精确断言成功行和失败 manifest 的关键字段。
- [Risk] 机械拆分可能只移动代码而不简化 → 以主编排函数行数、职责数量和重复分支减少作为审查依据，不引入额外公共抽象。

## Migration Plan

本变更无数据迁移。先增加失败的私有边界测试，再逐个提取 Dataset、Storage、ImportPipeline 与 LabelImg 实现并保持测试绿色；完成后运行完整 PR 门禁。若出现回归，可按模块提交回退，磁盘产物和用户调用方式无需迁移。

## Open Questions

无；公开边界与成功标准已由全项目重构方案确定。
