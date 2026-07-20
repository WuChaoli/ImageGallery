## Context

`DatasetManager` 已把 Repo/Dataset 控制面与 Dataset 历史协议拆入私有协作者，但 `manager.py` 仍直接实现 Tag Definition SQL、VectorField 定义及当前值、Repo Schema 锁、DatasetView IO 和 Dataset 范围向量生成。这些职责共享 manager 所有的 Engine、Catalog、StorageManager 与 ModelManager，却具有不同的事务和一致性边界；公开模型对象仍必须只回引用原 `DatasetManager`。

## Goals / Non-Goals

**Goals:**

- 将五组扩展职责拆入职责单一的包内私有协作者，并让 `DatasetManager` 保持跨组件领域编排。
- 保持公开导出、签名、异常类型与文本、对象回引用及 `__module__` 身份不变。
- 保持 Tag/VectorField SQL 事务、Repo 锁、固定 Snapshot 物理读取、Repo 当前向量合并及向量批量原子发布语义不变。
- 通过新增结构契约和既有/补充字符化测试验证重构前后行为一致。

**Non-Goals:**

- 不改变 migration、control schema、表结构、索引、约束或持久化格式。
- 不改变 public model/facade 的调用协议，不把私有协作者导出。
- 不增加通用 DAO、Unit of Work、依赖注入、搜索、ANN、缓存、删除、retention 或 GC。
- 不把 pending vectors 从历史协作者迁入 VectorStore。

## Decisions

### 每种一致性边界使用一个窄私有协作者

新增 `_tag_store.py`、`_vector_store.py`、`_schema_lock.py`、`_view_io.py` 和 `_embedding.py`。它们分别持有执行职责所需的最小依赖；不建立通用数据库抽象，因为各表的异常映射、事务和排序协议不同，统一抽象只会隐藏领域语义。

### Manager 保留跨组件编排和公开 handle identity

TagStore 与 VectorStore 返回包内 record，`DatasetManager` 继续构造 `TagDefinition`、`VectorField` 等公开对象并把自身作为 manager 回引用。`add_vector` 仍由 manager 在 RepoSchemaLock 内协调 Catalog、ModelManager 和 VectorStore；`add_column` 也继续由 manager 编排。这样避免私有 store 依赖公开 facade 或改变对象 identity。

### 保留现有 SQL 和锁生命周期

Tag 每个写操作继续使用独立 `engine.begin()`，`IntegrityError` 继续在原边界映射为相同异常文本。VectorStore 只管理 VectorField record 与 `asset_vectors` 当前值，不接触 Catalog、StorageManager 或 ModelManager。RepoSchemaLock 在非 PostgreSQL Backend 继续使用 manager 实例内 per-repo `RLock`；PostgreSQL Backend 继续在专用连接上取得相同 advisory lock key，并在 `finally` 中释放连接。

### ViewIO 显式区分固定物理行与当前向量

ViewIO 只按 `DatasetView.snapshot_id` 扫描固定 Iceberg Snapshot 的物理列；请求 VectorField 时一次批量读取 Repo 当前值，再按请求字段和 asset 顺序恢复结果。图片读取、校验和迭代继续通过固定行位置委托 StorageManager；`source_uri` 不参与位置解析。旧 View 的物理行保持冻结，而显式向量列保持读取 Repo 当前值。

### EmbeddingService 只执行已固定 Dataset 范围

Manager 先完成 field/source/branch/cross-Dataset 判定、冻结模型绑定校验，再把已固定 View 和依赖交给服务。服务筛选 existing、逐批验证和读取图片、运行推理，并只在所有批次成功后用单个 transaction 发布当前值和计算计数。批大小、值转换和错误传播保持原实现；服务不移动 Iceberg ref 或创建 Snapshot。

## Risks / Trade-offs

- [风险] 搬移 SQL 时改变事务或异常映射 → 机械保留语句、`engine.begin()` 与捕获边界，并补充冲突/跨 Repo/重复归档字符化测试。
- [风险] View 投影重排时改变行列顺序或空输入语义 → 固定交错字段、重复/未知字段、空集合与缺失向量测试，并验证批量查询。
- [风险] Embedding 拆分后校验晚于 IO 或出现部分发布 → Manager 保留前置判定，服务先完整计算后单事务发布，并覆盖失败与大批量场景。
- [风险] 组件过多增加装配噪声 → 每个组件只对应一个已有一致性边界，不添加接口层或通用基类；Manager 保留薄委托。
- [权衡] `DatasetManager` 保留若干私有适配方法 → 公开模型的调用关系无需变化，降低纯重构风险。

## Migration Plan

1. 先增加私有组件装配/职责结构测试及高风险字符化测试，并确认因组件尚不存在而失败。
2. 按 Tag、Vector、Schema Lock、View IO、Embedding 顺序机械迁移实现，每步运行聚焦测试。
3. 更新模块导航，完成默认、完整、覆盖率和真实 Dataset Backend 验收。

无需数据迁移；回滚本次代码提交即可恢复原单文件实现。

## Open Questions

无。
