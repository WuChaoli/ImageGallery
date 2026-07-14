## Context

内置算子当前使用 `category.operator_check` 长名格式，17 个算子分布在 6 个分类（format、size、quality、content、metadata、duplicate）中。名称同时承载分类信息（前缀）和能力描述（后缀），导致用户配置冗长。

TOML 配置文件将算子选择（`[cleaner].operators`）、业务配置（`[[operator]]`）和运行策略（`[operator_policies]`）分散在三处，用户需要理解三种不同语法（列表、数组表、带点键的子表）。

`_expand_selector()` 使用 `"." in selector` 判断输入是算子名还是分类名，短名不含 `.`，这个启发式规则需要替换。

## Goals / Non-Goals

**Goals:**
- 17 个内置算子使用短名作为主标识，旧长名使用时报错
- TOML 结构统一为 `[select]` + `[operators]` + `[runtime]` 三段式
- `_expand_selector()` 基于注册表精确匹配短名，不再依赖 `.` 启发式
- 全仓库搜索替换，所有测试、notebook、示例使用新名

**Non-Goals:**
- 不实现 YAML Recipe 系统（独立 change）
- 不实现 ActionRange 或 MetricSpec（独立 change）
- 不保留旧长名兼容层或 deprecation warning
- 不改变 `OperatorSpec` 数据结构（`category` 字段保留）

## Decisions

### 决策 1：短名映射规则

从长名提取 `operator_check` 后缀、去掉 `_check` 作为短名。映射表：

| 长名 | 短名 |
|------|------|
| `format.decode_check` | `decode` |
| `size.dimension_check` | `dimension` |
| `size.aspect_ratio_check` | `aspect_ratio` |
| `size.megapixel_check` | `megapixel` |
| `quality.blur_check` | `blur` |
| `quality.brightness_check` | `brightness` |
| `quality.contrast_check` | `contrast` |
| `content.blank_image_check` | `blank` |
| `quality.exposure_check` | `exposure` |
| `quality.noise_check` | `noise` |
| `content.mono_color_check` | `mono_color` |
| `content.border_padding_check` | `border_padding` |
| `format.animated_image_check` | `animated` |
| `metadata.orientation_check` | `orientation` |
| `duplicate.exact_duplicate_check` | `exact_duplicate` |
| `duplicate.perceptual_duplicate_check` | `perceptual_duplicate` |
| `duplicate.semantic_duplicate_check` | `semantic_duplicate` |

**理由**: 短名保留核心语义，去掉冗余的 `_check` 后缀。分类信息仍通过 `category` 字段保留，用于分类选择器。

### 决策 2：`_expand_selector` 改为注册表优先

改为：先查注册表精确匹配（短名） → 再查分类名展开 → 都不匹配则报错。`"." in selector` 改为仅作为旧名错误提示的判断依据。

**理由**: 短名不含 `.`，无法用旧的启发式规则。注册表精确匹配保证确定性。

### 决策 3：TOML 新结构

```toml
[select]
categories = ["quality", "duplicate"]

[operators]
blur = { min_score = 100.0 }
exact_duplicate = {}

[runtime]
batch_size = 128
fail_fast = false
```

- `[select]`: 按分类或 `"ALL"` 选择算子，与 `[operators]` 互斥
- `[operators]`: 显式列出算子及其配置覆盖，空 `{}` 表示使用默认值
- `[runtime]`: 拍平常用运行参数，消除嵌套的 `[node_policy.batch]` 等

**理由**: 单一 `[operators]` 表同时承载选择和配置，消除三处分散。空 `{}` 表达"使用默认但显式声明"。

### 决策 4：一次性 breaking change

不保留旧长名兼容。使用旧名时直接抛出 `ValueError`，提示对应短名。

**理由**: 项目处于开发阶段，用户基数极小。一次性迁移比维护兼容层更干净。

### 决策 5：实施顺序

1. 先迁移 `builtin.py` 算子名 + `_expand_selector` 逻辑（核心）
2. 再迁移 `toml_config.py`（TOML 新结构）
3. 最后全仓库搜索替换（测试 + notebook + 示例）

**理由**: 先核心后外围，每步可验证。如果先改测试，核心还没改会导致大面积失败。

## Risks / Trade-offs

- **[风险] 全仓库搜索替换遗漏** → 迁移完成后运行全量测试，任何遗漏会被测试失败捕获
- **[风险] 短名与未来算子冲突** → 短名唯一性由 `OperatorRegistry` 在注册时保证
- **[取舍] 不保留 `category.operator_check` 格式的任何痕迹** → `category` 字段保留在 `OperatorSpec` 中，分类选择器仍可用
- **[取舍] TOML 结构 breaking change** → 旧 TOML 文件不再兼容，但项目尚无外部用户
