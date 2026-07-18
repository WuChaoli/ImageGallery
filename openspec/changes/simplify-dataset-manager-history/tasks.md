## 1. 协议基线

- [x] 1.1 增加私有历史协作者装配结构测试并确认实现前失败
- [x] 1.2 运行既有 commit、clone、checkpoint、branch、rollback 与中断恢复特征测试建立基线

## 2. 历史职责拆分

- [x] 2.1 新增私有 DatasetHistory 协作者并迁移历史读取、commit、clone、checkpoint、branch 与 rollback
- [x] 2.2 迁移候选 Snapshot、pending vector 发布与 durable recovery，保持 intent、Hook、事务和 Iceberg ref 顺序
- [x] 2.3 将 DatasetManager 收敛为薄委托并确认 Tag、VectorField、embed 与 View IO 边界未改变

## 3. 验证与收敛

- [x] 3.1 运行目标测试、公开 API 契约、format、lint、docs、默认 test 与 coverage
- [x] 3.2 运行 test-all 和 dataset-backend，确认执行测试零失败、源码覆盖率不低于 90%、diff coverage 不低于 80%
- [x] 3.3 审查差异、OpenSpec strict validate、完成中文提交并清理工作树
