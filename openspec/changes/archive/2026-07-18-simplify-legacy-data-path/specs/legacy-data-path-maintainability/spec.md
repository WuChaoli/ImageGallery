## ADDED Requirements

### Requirement: 旧数据链路内部职责分离

系统 SHALL 将表格格式 I/O、单记录导入、导入产物写出、Pascal VOC XML 与 LabelImg 表格值规范化组织为私有且领域内聚的实现边界，公开领域对象只保留编排和契约职责。

#### Scenario: Dataset 表格读写
- **WHEN** `Dataset.load()`、`Dataset.write()` 或 `Dataset.to_frame()` 处理 Parquet、CSV、JSONL
- **THEN** 系统 SHALL 通过私有表格 I/O 边界完成格式判定与 pandas 读写，并保持原返回和异常语义

#### Scenario: ImportPipeline 编排
- **WHEN** `ImportPipeline.run()` 处理多个来源记录
- **THEN** 系统 SHALL 将单记录导入和标准产物写出分离，同时保持输入顺序、逐项失败隔离及成功/失败计数

#### Scenario: LabelImg 互操作
- **WHEN** LabelImg Loader/Exporter 读取或写出 Pascal VOC 目录
- **THEN** 系统 SHALL 分离 XML、坐标和表格值处理职责，同时保持 `raw.parquet`、`images/`、`annotations/`、`labeled.parquet` 与失败报告协议

### Requirement: 旧数据链路公开语义稳定

重构 SHALL 保持相关包的 `__all__`、公开函数/类/方法签名、返回值、异常语义、`image_uri`/`source_uri` 含义以及新旧平台隔离边界。

#### Scenario: 公共接口契约验证
- **WHEN** 在 Python 3.10 上检查 storage、dataset、importers、schemas、annotations、visualization 与 reports 公共接口
- **THEN** 导出符号和公开签名 SHALL 与重构前基线一致

#### Scenario: LabelImg round-trip
- **WHEN** 带 `relative_xyxy` bbox 的 Dataset 导出到 Pascal VOC 后再加载
- **THEN** label、bbox、pose、truncated、difficult 与图片尺寸 SHALL 保持既有 round-trip 语义

#### Scenario: URI 与平台边界
- **WHEN** 旧数据链路导入、读取或导出本地及 S3 图片
- **THEN** `image_uri` SHALL 继续作为主引用，`source_uri` SHALL 只用于追溯，且系统 MUST NOT 隐式构造 DatasetManager 类型

### Requirement: 重构质量门禁

旧数据链路重构 SHALL 通过仓库默认质量门禁，且新增或修改源代码 SHALL 获得足够测试覆盖。

#### Scenario: 完整验证
- **WHEN** 变更准备提交
- **THEN** format、lint、docs、默认 test SHALL 全部通过，源代码覆盖率 SHALL 不低于 90%，diff coverage SHALL 不低于 80%
