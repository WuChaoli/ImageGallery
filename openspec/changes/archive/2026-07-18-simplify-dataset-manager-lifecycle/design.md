## Context

`DatasetManager` 同时保存 Engine、Catalog、StorageManager 和 ModelManager 生命周期状态，并直接实现 Repo、Dataset、Prefix、operation recovery、history、schema、vector 和 view IO。`models.py` 中的公开 handle 已经只做门面委托，因此本阶段可以保持所有公开对象不变，只收敛 manager 内部的控制面职责。

约束是公开导出、签名、返回类型、异常类型/文本、控制面表结构、Iceberg namespace/table 命名、operation intent/phase 数据以及资源关闭次数全部不变。新平台继续与旧 `image_gallery.dataset` / `storage` 独立。

## Goals / Non-Goals

**Goals:**

- 让 `DatasetManager` 保留公开生命周期和领域编排，移除重复 SQL/row mapping/operation 状态更新细节。
- 用私有 repository 协作对象集中 Repo/Dataset/Prefix 的控制面读写和可见性规则。
- 用私有 operation journal 集中 durable operation 的状态机写入，不改变恢复分派和幂等协议。
- 为后续 history 与 vector 两个顺序阶段建立窄而稳定的内部依赖边界。

**Non-Goals:**

- 不改变任何公开 API、异常、默认值、持久化 schema 或事务边界。
- 不重新设计 operation recovery，不引入通用 Unit of Work、DAO 框架或依赖注入容器。
- 不修改 commit/clone/rollback 算法、Tag/VectorField 规则、embedding 或 view 扫描语义。
- 不合并旧平台和 DatasetManager 平台。

## Decisions

### 1. DatasetManager 保持唯一公开门面

公开 constructors、factory、context manager、Repo 查询和 recovery 入口仍定义在 `manager.py`。新增协作对象全部放在下划线命名模块中，不从 `dataset_manager.__init__` 导出；公开 handles 仍持有原 `DatasetManager` 引用，因此调用链和对象 identity 不变。

### 2. repository 协作对象只封装控制面职责

私有 repository 对象集中 Repo/Dataset row mapping、可见记录查询、名称规范化冲突、Prefix 绑定/恢复和控制面登记。Catalog namespace/table 创建以及需要跨 Iceberg/control plane 的领域编排仍由 `DatasetManager` 决定，避免把新对象扩张为第二个 manager。

### 3. operation journal 只拥有持久化状态转换

私有 journal 提供 start、update intent、record phase、finalize 和 fail 五类窄操作，继续写入现有 `dataset_operations` 与事件表。恢复动作选择和每种 operation 的补偿逻辑留在 `DatasetManager`，journal 不感知 commit、clone 或 rollback 领域结构。

### 4. 以 characterization test 固定跨资源语义

新增测试通过公开入口和真实本地控制面观察资源关闭、隐藏记录、Prefix 重启恢复以及 operation intent/phase/final/failed 状态；不直接断言新增私有类的调用次数。现有 backend integration tests 继续证明 PostgreSQL/PyIceberg 行为。

## Risks / Trade-offs

- [移动 SQL 可能改变 transaction 边界] → 协作对象接收现有 Engine，并保持每个原方法的 `engine.begin()` 边界与语句顺序。
- [operation 状态抽取可能丢失失败上下文] → characterization tests 固定 intent、phase、failed 状态和幂等 finalize/fail 结果。
- [repository 对象可能形成宽泛 DAO] → 只承载 Repo/Dataset/Prefix 三类控制面职责，不接收 history、Tag 或 vector 操作。
- [后续顺序 PR 基线耦合] → 本阶段先独立通过全部门禁并发布，history 和 extensions 分支从本阶段 head 创建。

## Migration Plan

无需调用方或数据迁移。先提交 characterization tests，再逐组提取 operation journal 和 repository 控制面；每组保持测试全绿。验证失败时可回退私有委托，现有数据库和 Iceberg 数据不受影响。

## Open Questions

无。阶段顺序和公开语义不变已由全项目重构方案确认。
