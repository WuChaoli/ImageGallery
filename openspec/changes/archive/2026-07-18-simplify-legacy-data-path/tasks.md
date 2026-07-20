## 1. Characterization 与私有边界

- [x] 1.1 增加 Dataset 私有表格 I/O 的失败测试并验证 Parquet/CSV/JSONL 分派语义
- [x] 1.2 增加 ImportPipeline 单记录与产物边界的失败测试并固定成功/失败字段语义
- [x] 1.3 增加 LabelImg 私有 XML/表格规范化边界的失败测试并固定 round-trip
- [x] 1.4 增加 Storage 通用批量执行器的失败测试并固定逐项异常隔离

## 2. 内部实现简化

- [x] 2.1 提取 Dataset 私有表格 I/O 模块并保持 Dataset 公开签名与行为
- [x] 2.2 提取 ImportPipeline 单记录导入与产物写出职责，缩短主编排流程
- [x] 2.3 提取 LabelImg Pascal VOC 与表格值私有模块，保留原 helper 导入路径
- [x] 2.4 复用 Storage 私有批量执行器，消除读写/存在/删除异常隔离重复

## 3. 契约与质量验证

- [x] 3.1 运行 storage、dataset、importers、schemas、annotations、visualization 与相关清洗集成测试
- [x] 3.2 运行公共 API contract、format、lint、docs 和 OpenSpec strict validation
- [x] 3.3 运行默认 test 与 coverage，确认源代码覆盖率 >=90%、diff coverage >=80%
- [x] 3.4 审查 diff、清理临时产物并创建中文提交
