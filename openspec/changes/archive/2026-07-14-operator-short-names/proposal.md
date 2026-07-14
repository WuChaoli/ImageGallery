## Why

内置算子使用 `category.operator_check` 长名格式（如 `quality.blur_check`），TOML 配置中算子信息分散在 `[cleaner]`、`[[operator]]`、`[operator_policies]` 三处。短名和结构化 TOML 能降低用户认知成本，让配置文件更直观。项目处于开发阶段，一次性 breaking change 成本最低。

## What Changes

- **BREAKING**: 17 个内置算子从长名迁移到短名（`quality.blur_check` → `blur`），旧长名不再支持，使用时抛出 `ValueError`
- **BREAKING**: TOML 配置结构重构为 `[select]` + `[operators]` + `[runtime]` 三段式，消除旧的 `[cleaner]` + `[[operator]]` + `[node_policy]` + `[operator_policies]` 分离结构
- `_expand_selector()` 改为先查注册表精确匹配短名、再查分类展开，不再依赖 `.` 区分名称和分类
- `build_cleaner_toml_template()` 适配新结构，输出 `[select]` + `[operators]` + `[runtime]` 格式
- 全仓库 ~100 处引用搜索替换（tests ~25、notebooks ~25、examples ~18、builtin.py ~34）

## Capabilities

### New Capabilities

_无新增 capability_

### Modified Capabilities

- `cleaning-operators`: 算子短名命名（PLANNED → 实现），17 个算子使用短名，旧长名报错
- `cleaning-config`: TOML 结构优化为 `[select]` + `[operators]` + `[runtime]` 三段式

## Impact

- **代码**: `builtin.py`（算子 name 字段 + PreviewPolicy 键）、`selection.py`（`_expand_selector` 逻辑）、`toml_config.py`（`CleanerConfig` 结构 + 解析函数 + 模板生成）
- **测试**: `tests/unit/cleaning/test_toml_config.py`、`tests/unit/cleaning/test_selection.py`、`tests/unit/operators/test_builtin.py` 以及所有引用长名的集成测试
- **示例和 Notebook**: `examples/cleaning_runtime.toml`、`notebooks/_helpers/cleaning_configs.py`、所有 notebook 和 example 中的算子引用
- **依赖**: 无新增依赖
