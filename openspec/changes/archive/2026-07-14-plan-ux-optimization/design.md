# Design: plan-ux-optimization

## Context

当前清洗包的算子命名使用 `category.operator_check` 长名格式（如 `quality.blur_check`），运行模型为阻塞式 `run()` 直接返回 `CleanerResult`，配置入口为 Python API（BasicCleaner + TOML）。用户反馈需要更友好的 recipe 驱动体验。

superpowers/ 中的 `cleaning-user-experience-optimization` 计划（1208 行，74 步）已完成详细设计但尚未实现。本 change 将其转化为 openspec 规范。

## Goals

- 算子主标识迁移为短名（`blur`、`dimension`、`exact_duplicate` 等）
- 引入 YAML Recipe 作为用户友好的配置入口
- `run()` 改为非阻塞返回 `CleanerRun`，支持 stop/progress/resume
- 引入 `RunStore` 三种存储模式（memory/temporary/disk）
- 引入 `MetricSpec` 元数据区分用户可调参数类型
- 支持 `export("ALL")` 批量导出
- 增加 `before_run_check()` 生命周期钩子

## Non-Goals

- 不实现重复图保留策略增强
- 不实现 training/export 节点（YOLO/COCO/LabelImg）
- 不保留旧长名兼容（破坏式变更）
- 不引入 `run_and_export` 类一键 API

## Key Decisions

### D1: 短名映射规则

长名到短名的映射为去掉 category 前缀和 `_check` 后缀：
- `quality.blur_check` → `blur`
- `duplicate.exact_duplicate_check` → `exact_duplicate`
- `format.decode_check` → `decode`

category 名称（format/size/quality/content/metadata/duplicate）保留为选择器分组。

### D2: YAML Recipe 是用户友好入口，不是内部配置的 YAML 版

`CleanerRecipe.from_yaml()` 解析用户友好的 YAML 格式，编译为内部 operator selector 列表。YAML 支持：
- 区间规则语法：`"[0, 0.3]"`、`"(0.3, 0.6]"`
- 绝对阈值块：`drop: {min_width: 256}`
- 布尔/分组类：`action: drop`
- 运行默认值：`run.storage`、`run.output_dir`、`run.cache_root`

### D3: 非阻塞运行模型

```
run() → CleanerRun（后台线程）
  .wait() → CleanerResult
  .stop() → stopping → stopped
  .progress → RunProgress
  .result → CleanerResult | CleanerRunNotReadyError

run_sync() → CleanerResult（阻塞，等价于 run().wait()）
```

### D4: RunStore 三种模式

| 模式 | 持久化 | 默认 | 用途 |
|------|--------|------|------|
| memory | 无 | 否 | 测试/一次性 |
| temporary | 临时目录 | **是** | 日常使用 |
| disk | 用户指定路径 | 否 | 长期保存/resume |

memory 模式下语义算子应报错（需要文件系统存放 embedding/Faiss index）。

### D5: MetricSpec 区分用户心智模型

- **absolute**：尺寸等自然单位（min_width=256 就是 256px）
- **relative**：主观质量分（`[0, 0.3]` 映射到内部绝对范围）
- **categorical**：布尔/分组类（decode_ok、duplicate_group）

### D6: export("ALL") 批量导出

一次调用导出 full/clean/review/dropped 四个 Dataset，默认列与输入 Dataset 保持一致，计算/评估列由用户显式选择。

## Risks

- **[破坏式变更]** → 短名迁移不保留旧名兼容，所有测试和示例需同步更新
- **[非阻塞运行复杂度]** → 后台线程的异常处理和状态同步需要仔细设计
- **[YAML 与 TOML 双轨]** → 需明确两者定位：TOML 是内部配置，YAML 是用户 recipe
