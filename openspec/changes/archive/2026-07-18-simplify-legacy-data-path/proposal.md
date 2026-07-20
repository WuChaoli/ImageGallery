## Why

旧数据链路已经稳定承载 Storage、Dataset、Importers 与 LabelImg 互操作，但核心流程仍集中在少数较长函数和单文件中，导致 I/O、校验、转换与产物写出职责耦合。当前全项目分阶段重构需要先收敛这些内部边界，降低后续维护成本，同时不改变现有用户代码的语义。

## What Changes

- 将 Dataset 表格格式读写分派收敛到私有 I/O 边界，保持 `Dataset` 公开 API 不变。
- 将 ImportPipeline 的单记录导入与产物写出从主编排流程中分离，保持逐项失败隔离和 raw Dataset 契约不变。
- 将 LabelImg 的 Pascal VOC XML、表格值规范化和目录编排拆分为内聚的私有模块，同时保留原导入路径和 round-trip 语义。
- 简化 Storage 批量操作中的重复异常隔离逻辑，保持逐项结果结构与错误语义不变。
- 增加针对私有边界和公共语义的 characterization tests，并以源代码覆盖率不低于 90%、diff coverage 不低于 80% 作为门禁。

## Capabilities

### New Capabilities
- `legacy-data-path-maintainability`: 约束旧数据链路内部职责分离及其公开契约、URI 语义和 LabelImg 互操作保持不变。

### Modified Capabilities

无。

## Impact

影响 `src/image_gallery/storage/`、`dataset/`、`importers/` 与 `annotations/` 的内部实现及对应单元测试；`schemas/`、`visualization/`、`reports/` 仅作为契约边界验证，不引入新行为。所有现有 `__all__`、公开函数/类/方法签名、返回值、异常语义及 `image_uri`/`source_uri` 含义保持不变，不引入新依赖，也不触及 DatasetManager 新平台。
