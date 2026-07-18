## 1. 协议基线

- [x] 1.1 增加五个私有协作者的装配与职责边界测试并确认实现前失败
- [x] 1.2 补充 Tag、Vector、锁、View IO 与 Embedding 高风险语义字符化测试并建立基线

## 2. 存储与锁职责拆分

- [x] 2.1 新增 TagStore，迁移 Tag Definition SQL 与 active 校验并保持事务和异常映射
- [x] 2.2 新增 VectorStore，迁移 VectorField record 与 Repo 当前向量 CRUD
- [x] 2.3 新增 RepoSchemaLock，迁移本地 RLock 和 PostgreSQL advisory lock 生命周期

## 3. View 与向量生成职责拆分

- [x] 3.1 新增 ViewIO，迁移固定 Snapshot 扫描、投影、当前向量批量合并和图片 IO
- [x] 3.2 新增 EmbeddingService，迁移 existing 筛选、批量可信推理、原子发布和计数
- [x] 3.3 收敛 DatasetManager 为薄委托并保留跨组件编排、公开 handle identity 与前置校验

## 4. 验证与收敛

- [x] 4.1 运行聚焦测试、公开 API 契约、format、lint、docs、默认 test 与 coverage
- [x] 4.2 运行 test-all 和 dataset-backend，确认执行测试零失败、源码覆盖率不低于 90%、diff coverage 不低于 80%
- [x] 4.3 同步模块文档、审查差异、OpenSpec strict validate、完成中文提交并清理工作树
