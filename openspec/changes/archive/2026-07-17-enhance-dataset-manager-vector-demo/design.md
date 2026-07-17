## Context

现有综合 Notebook 已能在真实 Backend 上执行 Dataset 完整生命周期，并已包含 `Dataset.generate_embed()` 的最短 happy path。但向量章节只有一个说明单元和一个代码单元，未把新增 API 的边界与持久化语义转化为可观察、可执行的教学步骤。

## Goals / Non-Goals

**Goals:**

- 在现有 Notebook 中完整演示模型定义、VectorField 绑定、生成范围、跳过/覆盖、DataFrame 读取和重连恢复。
- 用断言证明向量生成不移动 Snapshot，避免示例只展示输出而不验证契约。
- 让真实 Backend Notebook 测试覆盖新增步骤，并保持演示可从干净 kernel 重复执行。

**Non-Goals:**

- 不新增 Notebook、模型 provider 或生产 Importer。
- 不演示故障注入、内容篡改、安全攻击或性能基准。
- 不修改 DatasetManager、ModelManager 或 StorageManager 的公共 API。

## Decisions

1. **扩充现有第 4 节，而非拆分新示例。** 用户可沿着同一批 20 张图片理解导入、版本和向量之间的关系；代价是单个 Notebook 稍长，但可通过多个短 Markdown/代码单元维持可读性。
2. **所有语义都用公开 API 和可见断言演示。** 读取模型冻结定义与 VectorField DTO，调用 `generate_embed`，通过 `scan(fields=[...])` 返回 DataFrame，并比较调用前后的 View/Snapshot；不访问数据库内部表。
3. **增量范围使用现有 experiment View。** 先在 main Head 生成，再对分支固定 View 调用，从计数和成员集合展示范围限制，不额外构造隐藏数据集。
4. **重连验证复用现有关闭/重连章节。** 重建客户端后检查恢复的模型定义、字段元数据和扫描出的当前向量，避免新增生命周期入口。
5. **Notebook 测试同时做结构和执行验证。** 单元测试检查中文章节及关键 API 片段，真实 Backend 集成测试继续从头执行 Notebook，防止文本与真实行为脱节。

## Risks / Trade-offs

- [重复运行会命中已存在资源或向量] → 继续使用测试隔离 Backend，并让 Notebook 对幂等注册和生成计数作明确断言。
- [分支成员与 main 重叠导致指定 View 全部被跳过] → 教学文字明确 Repo 当前向量按 asset_id 复用，并用结果计数展示这一语义，而不是假设每次都会生成。
- [Notebook JSON 手工编辑容易破坏结构] → 使用小型生成脚本只更新目标 cell 列表，随后执行 JSON 解析、结构测试和真实 Backend 测试。
