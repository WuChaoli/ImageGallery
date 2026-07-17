## 1. ModelManager 契约与测试骨架

- [x] 1.1 先编写 ModelDefinition 指纹稳定、持久化恢复、同配置幂等注册和同 ID 异配置拒绝的单元测试
- [x] 1.2 先编写 provider runtime 延迟加载、缓存、关闭以及关闭后拒绝推理的单元测试
- [x] 1.3 先编写模型输出数量、维度、dtype、NaN 和 Inf 校验失败的参数化测试
- [x] 1.4 实现公开 ModelManager、ModelDefinition、provider/runtime 协议和领域错误，并补齐公开导出与中文 Google 风格 docstring
- [x] 1.5 实现凭证引用隔离和配置指纹脱敏测试，确认公开 DTO、异常与日志不泄露明文凭证

## 2. VectorField 持久化与 Schema facade

- [x] 2.1 先编写 VectorField 强绑定 model_id、fingerprint、dimension、dtype、distance 的仓储集成测试
- [x] 2.2 修订 PostgreSQL 控制模型与初始 Alembic 迁移，持久化 Model/Storage Prefix 冻结定义，删除 validation set/output 并加入 VectorField 模型绑定元数据
- [x] 2.3 删除 validation DTO、验证比较逻辑、公开 write 入口及相关导出，确保没有遗留不可达代码
- [x] 2.4 先编写 `repo.schema.add_vector/get_vector/list_vectors` 的成功、幂等、未知模型、配置漂移和名称冲突测试
- [x] 2.5 实现 RepoSchema facade，并移除旧 VectorField 直接创建入口而不保留兼容 shim
- [x] 2.6 先编写 `dataset.schema.add_column/get_column/list_columns` 的成功、破坏性演进和跨普通列/向量重名测试
- [x] 2.7 实现 DatasetSchema facade，并移除旧普通列直接演进入口而不保留兼容 shim

## 3. DatasetManager 基础设施集成

- [x] 3.1 先编写 DatasetManager 注入 ModelManager、复用 StorageManager 和统一关闭资源的生命周期测试
- [x] 3.2 调整 DatasetManager 构造与工厂入口，使 Repo 和 View 能访问同一受控 ModelManager 与 StorageManager
- [x] 3.3 编写进程重启后自动恢复相同 model_id/prefix_id 原定义、配置漂移拒绝和离线资源不可达的集成测试

## 4. DataFrame 读取与 Commit

- [x] 4.1 先编写 scan/get_rows 返回 DataFrame、get_row 返回 Series、默认只读物理列和稳定字段顺序的测试
- [x] 4.2 先编写 fields 混合普通列与 VectorField、缺失向量为 None、未知/歧义字段拒绝和单次批量向量查询测试
- [x] 4.3 实现统一 fields 解析与固定 Snapshot 物理数据加 Repo 当前向量的 DataFrame 合并
- [x] 4.4 先编写 DataFrame Commit 显式 fields patch、未传 fields 完整 upsert、新行、no-op 和 Branch 基线冲突测试
- [x] 4.5 实现普通字段 patch/full Commit，并保持系统字段、asset_id、Storage 位置和 tag_ids 校验
- [x] 4.6 编写并实现 Commit 对 fields 或 frame 中 VectorField 的前置拒绝，确认 Dataset 与向量状态均不改变

## 5. Dataset 范围的向量生成

- [x] 5.1 先编写 `dataset.generate_embed(field)` 默认固定 main Head 全部成员且执行中 Branch 推进不改变范围的集成测试
- [x] 5.2 先编写指定 Branch Head、显式 source View、跨 Dataset View、source/branch 歧义、未知字段和冻结指纹漂移测试
- [x] 5.3 先编写通过 StorageManager 读取 View 冻结位置、校验 asset_id SHA-256 和相同 asset 跨 Dataset 复用的测试
- [x] 5.4 先编写 overwrite=false 跳过已有值、overwrite=true 替换值和 generated/updated/skipped 计数测试
- [x] 5.5 先编写多批推理任一读取/推理/输出校验失败时整次不发布且已有向量不变的原子性测试
- [x] 5.6 实现 `Dataset.generate_embed` 的 Head 固定、字段/模型解析、稳定成员枚举、可信图片读取、批量推理与单事务发布，并返回 source_snapshot_id
- [x] 5.7 验证 generate_embed 不创建或移动 Iceberg Branch、Snapshot、Checkpoint，旧 View 始终读取 Repo 当前向量

## 6. E2E、示例与文档

- [x] 6.1 扩展临时测试 importer E2E：导入、存储、读取、Branch、Version、Commit、Schema、模型注册、指定 View embedding 和混合 DataFrame 扫描
- [x] 6.2 覆盖 E2E 中同一 View 重复生成、显式覆盖、模型失败回滚和 Dataset Snapshot 不推进
- [x] 6.3 更新 `examples/` 中文 Notebook：自动探测 `.env`、提示复用或重建 PostgreSQL/pgvector、注册演示模型并演示默认 main Head 与显式 View 生成
- [x] 6.4 使用已提交的 20 张本地材料执行 Notebook smoke test，并确认示例不依赖 sample_1000 或网络
- [x] 6.5 同步 DatasetManager README、模块 AGENTS 导航和公开 API 文档，明确不支持全 Repo embedding 与向量当前值语义

## 7. 清理与交付验证

- [x] 7.1 搜索并删除 validation_outputs、validation_set、组合 Data+Vector Commit 和公开 VectorField.write 的残留引用
- [x] 7.2 逐项运行 format-check、lint、docs、test、coverage、security、package、package-validate 和 package-smoke
- [x] 7.3 运行 DatasetManager PostgreSQL/pgvector 容器集成测试、完整 E2E 与需要的 test-all，记录环境和结果
- [x] 7.4 审查 spec-to-task 映射和测试覆盖矩阵，确认每个 Scenario 至少有直接测试或明确的组合验收证据
- [x] 7.5 执行独立代码审查并修复所有 P1/P2 问题，再同步 specs/docs、归档 change、中文提交并更新原 PR
