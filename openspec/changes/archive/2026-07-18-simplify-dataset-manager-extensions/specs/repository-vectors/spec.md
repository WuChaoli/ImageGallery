## ADDED Requirements

### Requirement: 向量扩展职责拆分保持协议稳定

系统 SHALL 在把 VectorField 存储、Repo Schema 锁、DatasetView IO 和 Dataset 范围向量生成拆入私有协作模块后，保持公开导出、签名、返回对象回引用、异常文本、事务、并发、固定 Snapshot 物理行与 Repo 当前向量语义不变。

#### Scenario: VectorField 定义与当前值经私有存储执行
- **WHEN** 调用方创建、打开、列出 VectorField 或读取 Repo 当前向量
- **THEN** 系统保持名称规范、幂等与冲突行为、Repo 隔离、排序、缺失值和单事务发布语义

#### Scenario: Repo Schema 锁经私有锁组件执行
- **WHEN** 同 Repo 或不同 Repo 并发修改 Schema，或持锁操作异常退出
- **THEN** 系统保持同 Repo 串行、不同 Repo 独立、PostgreSQL advisory lock key 和连接释放行为

#### Scenario: View 合并固定物理行与当前向量
- **WHEN** 调用方从固定 DatasetView 扫描、按 asset_id 取行、读图、校验或迭代图片，并显式选择 VectorField
- **THEN** 系统保持 Snapshot 物理行、字段和资产顺序，同时批量合并 Repo 当前向量且缺失值为 `None`

#### Scenario: Dataset 范围生成经私有服务执行
- **WHEN** `Dataset.generate_embed` 已固定合法 source View 并通过冻结模型校验
- **THEN** 系统保持 existing 筛选、可信图片验证、批量推理、全请求原子发布与计数，并且不推进 Iceberg 历史
