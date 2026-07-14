## Context

当前清洗配置通过 TOML（`CleanerConfig`）或 Python API（`select_operators`）加载。TOML 面向开发者，但非技术用户需要更声明式的配方格式。Spec 中已定义四个 PLANNED 能力：ActionRange（区间语法）、MetricSpec（指标元数据）、CleanerRecipe（YAML 配方）和双级动作评估。

RunStore 存储模式也是 PLANNED 状态：当前 `CleaningRuntime` 硬编码使用文件系统（`cache_root / run_id`），测试中无法避免磁盘 IO。

`pyyaml` 尚未作为项目依赖。

## Goals / Non-Goals

**Goals:**
- ActionRange 独立可用，解析数学区间语法并支持 `contains()` 判断
- MetricSpec 描述每个算子指标的类型、范围和方向
- CleanerRecipe.from_yaml() 加载 YAML 配方，编译为内部 selector
- 双级动作评估基于 ActionRange 实现 drop > review > keep 优先级
- RunStore 抽象支持 memory / temporary / disk 三种模式
- 分步实施：① ActionRange → ② MetricSpec → ③ Recipe + 双级评估 → ④ RunStore

**Non-Goals:**
- 不实现 YAML 配方中的 storage 配置段（RunStore 通过 Python API 配置）
- 不实现非阻塞运行模型（独立 change）
- 不改变现有 evaluator 函数的签名

## Decisions

### 决策 1：ActionRange 作为独立模块

放在 `src/image_gallery/cleaning/action_range.py`，无外部依赖，纯正则 + 数学解析。

**理由**: ActionRange 是最小独立单元，可先于 Recipe 实现和测试。evaluator 可直接消费。

### 决策 2：MetricSpec 放在 operators 包

放在 `src/image_gallery/operators/metric_spec.py`，与 `OperatorSpec` 关联但独立定义。每个算子的 MetricSpec 在 `builtin.py` 中注册。

**理由**: MetricSpec 描述算子指标属性，与算子定义紧密相关。放在 operators 包便于和 builtin.py 一起维护。

### 决策 3：CleanerRecipe YAML 结构

```yaml
version: 1
run:
  output_dir: ./output
  cache_root: ./.cache
operators:
  - use: blur
    rules:
      drop: "[0, 0.3]"
      review: "(0.3, 0.6]"
  - use: dimension
    drop:
      min_width: 256
  - use: decode
    action: drop
```

编译为 selector 列表后传给 `select_operators()`。

**理由**: YAML 格式比 TOML 更适合嵌套结构。`use` 关键字明确指定算子名。`rules` 段使用 ActionRange 区间语法。

### 决策 4：RunStore 使用 Protocol 而非 ABC

定义 `RunStore` Protocol（write_table/read_table/write_json/read_json/materialize_dataset/cleanup），三个实现类：`MemoryRunStore`、`TemporaryRunStore`、`DiskRunStore`。

**理由**: Protocol 允许 duck typing，不需要强制继承。现有 `write_tables()` 等函数可以通过适配器接入。

### 决策 5：双级评估不修改现有 evaluator

新增 `evaluate_with_rules()` 函数，接受 ActionRange 规则和 MetricSpec，输出 action 列。现有 evaluator 保持单级（基于 config 的 action 字段），新函数用于 Recipe 场景。

**理由**: 现有 evaluator 已被 TOML 配置和 Python API 广泛使用。双级评估是 Recipe 新增能力，不应影响现有路径。

## Risks / Trade-offs

- **[风险] pyyaml 新增依赖** → pyyaml 是成熟稳定的包，社区广泛使用
- **[风险] 双级评估和现有单级评估共存造成混乱** → 文档明确区分：TOML/API 用单级，Recipe 用双级
- **[取舍] RunStore 完全替换现有文件系统路径** → 第一版 DiskRunStore 封装现有逻辑，MemoryRunStore 仅支持无 artifact 的算子
- **[取舍] ActionRange 不支持无穷区间** → 第一版足够，图片质量指标都有有限范围
