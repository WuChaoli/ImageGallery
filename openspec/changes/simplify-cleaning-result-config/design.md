## Context

`CleanerResult` 是清洗运行的只读公开门面，但当前 445 行实现直接处理路径构造、SQLite/JSON/Parquet 读取、relation/manifest/调试包导出、预览策略解析、结果解释和目录清理。`toml_config.py` 的 335 行实现也同时处理文件入口、选择器、模板渲染和六类嵌套策略解析。两者都把稳定的公开入口与易变化的底层细节绑在同一文件中。

约束是 `image_gallery.cleaning` 的导出、公开签名、返回类型、异常类型/文本以及 Parquet、JSON、SQLite 和 HTML 可观察语义不变；本阶段基于已完成的 Cleaning Runtime 重构，不再修改运行编排。

## Goals / Non-Goals

**Goals:**

- 用公共行为与磁盘产物 characterization tests 固定 Result、preview/export 和 TOML/YAML 配置边界。
- 让 `CleanerResult` 保留门面编排，把产物访问、复制/打包和预览准备下沉到私有模块。
- 让 `CleanerConfig` 保留配置入口，把 TOML 模板和 `NodePolicy` 嵌套解析下沉到私有模块。
- 降低高耦合文件行数、重复路径拼装和分支复杂度。

**Non-Goals:**

- 不增加 `export("ALL")` 等尚处于 planned 状态的能力。
- 不改变 `CleanerResult`、`CleanerConfig`、`CleanerRecipe` 的公开签名或支持的配置结构。
- 不改变运行目录、manifest/state schema、预览 HTML 布局、算子选择规则或 Dataset 导出协议。
- 不修改 Cleaning Runtime、operators 或 DatasetManager。

## Decisions

### 1. Characterization tests 只观察公开入口和磁盘边界

测试通过真实临时 Parquet、JSON、SQLite、YAML/TOML 文件调用公开方法，覆盖缺失文件回退、严格列表校验、operator preview 过滤、配置互斥与嵌套策略错误。通过受控 mutation 证明测试会在语义漂移时失败，不断言私有 helper 的调用关系。

替代方案是直接为新私有模块写测试；这会把测试锁定在本轮内部结构上，削弱未来继续简化的空间。

### 2. 用私有 Result 产物访问对象集中路径与解析

引入模块私有只读对象，持有 `run_id` 和 `cache_root`，统一提供运行路径、表、operator outputs、parameter manifest、relation names 和状态读取。`CleanerResult` 继续决定各公开方法的业务编排，但不再重复定位与解析持久化产物。

替代方案是增加更多模块级函数；它能移动代码，却仍需在每次调用重复传递 `cache_root`、`run_id` 和路径，未能收敛数据依赖。

### 3. 导出与预览采用窄职责私有函数

文件复制、relation 导出和调试包打包归入私有导出模块；operator preview 的列选择、过滤、排序和选项解析归入私有预览模块。公开 `CleanerResult` 方法只组装稳定输入并委托，Dataset fallback 文件名和异常文本原样保留。

替代方案是把所有能力放入一个大型 `ResultService`；这只会把单文件过载转移到另一个文件，并形成新的宽泛抽象。

### 4. TOML 入口、模板和策略解析分层

`toml_config.py` 保留 `CleanerConfig`、`build_cleaner_toml_template` 与选择/operators 段入口；模板值格式化移动到私有模板模块，`NodePolicy` 及其嵌套 policy 的类型校验移动到私有策略解析模块。公开函数仍从原模块可用，所有错误文本保持一致。

替代方案是合并 YAML recipe 与 TOML 配置模型；两者面向不同用户输入并有独立公开语义，合并会扩大风险且不属于本阶段。

## Risks / Trade-offs

- [私有对象可能无意改变缺失文件回退] → 用缺失 manifest/table/state 的 characterization tests 固定空映射、最小表和 running 状态。
- [预览拆分可能改变过滤与排序顺序] → 以 operator action、filters、stable sort、max rows 和 dataset fallback 的真实 HTML 测试锁定顺序。
- [策略解析移动可能改变异常类型或文本] → 参数化测试覆盖全部 runtime policy 类型错误，并比较原有错误片段。
- [拆分增加私有文件数量] → 每个文件只承载单一变化轴，不新增公共导出或通用框架。

## Migration Plan

无需数据或调用方迁移。先提交 characterization tests，再提取私有实现；验证失败时可直接回滚私有模块和门面委托，既有运行产物保持可读。

## Open Questions

无。公开和持久化边界已由全项目重构方案确认。
