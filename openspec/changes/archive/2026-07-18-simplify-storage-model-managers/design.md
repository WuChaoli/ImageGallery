## Context

StorageManager 和 ModelManager 是新 DatasetManager 平台的独立基础设施。当前实现已经有清晰公开契约，但两个 manager 文件都直接包含多种内部职责：StorageManager 在一个类中处理 Prefix registry、路径规则、Backend client、file/S3 IO、managed promote/recovery；ModelManager 同时处理 SQL 持久化和 provider runtime 生命周期。后续 DatasetManager 分阶段重构会持续依赖这些边界，因此本阶段先固定行为并降低内部耦合。

约束是公开 `__all__`、公开类/方法签名、返回值和异常不变；StorageManager 的路径安全、内容寻址、凭证隔离和恢复语义不变；ModelManager 的数据库 schema、冻结定义、runtime 缓存、输出校验和资源所有权不变；旧 `storage` 平台与 DatasetManager 实现不在本阶段修改。

## Goals / Non-Goals

**Goals:**

- 用 characterization tests 固定 file/S3 后端、路径、managed recovery、Engine 迁移和 provider 生命周期的现有语义。
- 让公开 manager 只负责稳定用例编排，把路径/Backend 与模型 runtime 细节收敛到私有模块。
- 降低 manager 文件中的 Backend 分支、重复校验和资源关闭职责耦合。
- 保持全仓覆盖率不低于 90%，变更行覆盖率不低于 80%。

**Non-Goals:**

- 不新增 Storage Backend、模型 provider、Prefix 生命周期能力或模型注册能力。
- 不修改 DatasetManager、数据库 schema、对象路径格式、旧 `image_gallery.storage` 或公开 DTO。
- 不保留新私有模块路径的兼容性承诺，也不把私有 helper 导出到包级 API。

## Decisions

### 1. StorageManager 保持门面，私有 BackendStore 统一 Backend 特定操作

新增私有路径模块集中相对路径规范化、file root containment、对象路径和托管路径构造；新增私有 BackendStore 负责 fsspec client 构造/缓存/关闭，以及 file/S3 普通读写、managed promote 和 staging recovery。StorageManager 继续负责 Prefix registry、公开参数校验、内容身份与公开异常编排。

选择私有协作者而不是公开 Backend 抽象，是因为当前只支持 file/S3 且没有新增 Backend 的需求；公开抽象会扩大 API 和测试矩阵。也不只提取零散函数，因为 client cache 和关闭生命周期需要一个明确所有者。

### 2. 路径安全在进入 Backend IO 前完成

所有公开相对路径先经同一私有规范化函数处理，file 路径再经 root containment 检查；保留命名空间只允许内部 managed/recovery 和公开读取既有托管对象。BackendStore 只接收已经按用途验证的路径，避免 file/S3 分支各自复制规则。

选择保留当前异常类型和验证顺序，不借重构扩大或放宽规则，以确保调用方观察到的错误语义不漂移。

### 3. ModelManager 将冻结定义和 RuntimePool 分离

`ModelDefinition` 与 `ModelRuntime` 继续实际定义在 `manager.py`，保持 `__module__`、pickle GLOBAL 路径和类型身份；SQLAlchemy table 与 row 映射移入私有定义模块。provider factory 选择、凭证解析、runtime 缓存、批量输出校验和 runtime 关闭移入私有 RuntimePool。ModelManager 保持注册、查询、Engine 绑定和公开关闭门面，并继续决定是否拥有 Engine。

选择 RuntimePool 而不是为每个 provider 建立插件框架，因为当前 provider 已由 `RuntimeFactory` 映射注入；更宽的插件抽象不属于本阶段。

### 4. Characterization-first 验证私有拆分

先补充只观察公开行为的 characterization tests，固定 S3 managed recovery、Prefix 恢复冲突、Engine 绑定迁移、凭证只解析一次、非法输出不返回部分结果、重复关闭只释放一次。通过临时 mutation 破坏 recovery 与 runtime cache，确认测试会因语义断裂而失败，再恢复实现并保持全量回归为 GREEN；测试不锁定私有模块名或协作者字段。

## Risks / Trade-offs

- [风险] 私有拆分改变 IO 前的验证或异常顺序 → 用 characterization tests 覆盖不安全路径、对象存在、缺失对象和内容不一致，公开契约测试锁定签名。
- [风险] fsspec/s3fs 关闭方式存在实现差异 → 保留 `close()`、`close_session()` 与 `_s3creator` finalizer 分支，并运行资源生命周期测试与 `test-all`。
- [风险] 公开类型迁移改变 `__module__` 或 pickle GLOBAL 路径 → 保持类型实际定义在 manager 模块，并显式覆盖模块身份和 pickle 往返。
- [风险] Engine 迁移或 runtime cache 拆分改变资源所有权 → 覆盖内部/外部 Engine、重复关闭和 provider runtime 关闭次数。
- [权衡] 新增私有文件增加文件数量 → 换取职责边界清晰；每个私有模块只对应一个稳定职责，不建立通用框架。

## Migration Plan

1. 添加 characterization tests，并用临时 mutation 验证关键语义断裂会被测试捕获。
2. 提取 StorageManager 私有路径和 BackendStore，运行 storage_manager 与相关 DatasetManager 测试。
3. 提取 ModelManager 私有定义和 RuntimePool，运行 model_manager 与 lifecycle/embedding 测试。
4. 运行公开接口契约、默认测试、coverage、lint、docs 和 `test-all`。
5. 若任一契约回归，回退私有委托并保留 characterization tests；没有数据迁移或部署步骤。

## Open Questions

无。
