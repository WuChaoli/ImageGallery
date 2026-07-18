## 1. Characterization 与公开边界

- [x] 1.1 补充 StorageManager 的 S3 managed recovery、Prefix 恢复冲突和关闭生命周期 characterization tests，并用 mutation 观察 RED
- [x] 1.2 补充 ModelManager 的 Engine 绑定、runtime 复用/凭证解析、非法输出和重复关闭 characterization tests，并用 mutation 观察 RED
- [x] 1.3 运行公开接口契约测试，记录重构前 package 导出与公开方法签名基线

## 2. StorageManager 私有职责拆分

- [x] 2.1 提取相对路径、file root containment、对象路径和 managed/staging 路径到私有路径模块
- [x] 2.2 提取 Backend client 构造、缓存、file/S3 IO、managed promote/recovery 和关闭到私有 BackendStore
- [x] 2.3 将 StorageManager 收敛为 Prefix registry、公开校验、内容身份和 BackendStore 编排门面
- [x] 2.4 运行 StorageManager 与相关 DatasetManager 测试，确认路径、内容完整性、恢复和两平台隔离契约保持

## 3. ModelManager 私有职责拆分

- [x] 3.1 提取冻结模型定义、SQLAlchemy table 和 row 映射到私有定义模块
- [x] 3.2 提取 provider runtime 加载/缓存、凭证解析、输出校验和关闭到私有 RuntimePool
- [x] 3.3 将 ModelManager 收敛为定义持久化、Engine 绑定和 RuntimePool 编排门面
- [x] 3.4 运行 ModelManager、DatasetManager lifecycle 与 embedding 测试，确认所有权和输出契约保持

## 4. 全量验证与收尾

- [x] 4.1 运行 format-check、lint、docs、默认 test 与公开接口契约测试
- [x] 4.2 运行 coverage，确认全仓源码行覆盖率不低于 90%、变更行覆盖率不低于 80%
- [x] 4.3 运行 test-all 验证资源生命周期与慢速回归；按实际 Backend 影响评估并运行 dataset-backend
- [x] 4.4 严格校验 OpenSpec、审查 diff、清理临时产物并提交中文 commit
