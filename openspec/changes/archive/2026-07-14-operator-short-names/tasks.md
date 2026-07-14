## 1. builtin.py 算子名迁移

- [x] 1.1 修改 `src/image_gallery/operators/builtin.py` 中 `_builtin_specs()` 的 17 个 `OperatorSpec.name` 字段，从长名改为短名（如 `"quality.blur_check"` → `"blur"`），保留 `category` 字段不变
- [x] 1.2 修改 `_to_builtin_preview_spec()` 的 `policies` 字典键，从 17 个长名改为对应短名
- [x] 1.3 运行 `python -m ruff check src/image_gallery/operators/builtin.py` 确认无 lint 错误

## 2. selection.py 选择器逻辑改造

- [x] 2.1 修改 `src/image_gallery/cleaning/selection.py` 的 `_expand_selector()`：先尝试 `registry.get_operator(selector)` 精确匹配短名 → 成功则返回 `[selector]`；失败则查分类名展开；都失败则报错
- [x] 2.2 修改错误信息：当 selector 含 `.` 且不在注册表中时，提示"旧长名格式不再支持，请使用短名"
- [x] 2.3 运行 `tests/unit/cleaning/test_selection.py` 确认选择器逻辑正确

## 3. toml_config.py TOML 结构重构

- [x] 3.1 修改 `CleanerConfig` dataclass：将 `operators` + `operator_configs` 合并为新的字段结构（selectors + operator_configs），保持 `node_policy` 和 `operator_policies`
- [x] 3.2 重写 `from_mapping()`：解析新的 `[select]` 段（categories 列表）、`[operators]` 段（短名 → 内联配置表）、`[runtime]` 段（拍平参数映射到 NodePolicy）
- [x] 3.3 实现 `[select]` 和 `[operators]` 互斥校验：两段同时存在时抛出 ValueError
- [x] 3.4 重写 `build_cleaner_toml_template()`：输出可 round-trip 加载的 `[operators]` + `[runtime]` 新结构，算子配置用内联表格式 `{ key = value }`，空配置输出 `{}`
- [x] 3.5 移除旧的 `_parse_operators()`、`_parse_operator_configs()`、`_parse_operator_policies()` 函数，替换为新解析逻辑
- [x] 3.6 运行 `python -m ruff check src/image_gallery/cleaning/toml_config.py` 确认无 lint 错误

## 4. 测试迁移

- [x] 4.1 搜索替换 `tests/` 目录中所有长名引用（`quality.blur_check` 等 17 个）为对应短名
- [x] 4.2 更新 `tests/unit/cleaning/test_toml_config.py`：所有测试用例适配新 TOML 结构（`[select]` + `[operators]` + `[runtime]`）
- [x] 4.3 更新 `tests/unit/cleaning/test_selection.py`：验证短名精确匹配、分类展开、旧长名报错
- [x] 4.4 更新 `tests/unit/operators/test_builtin_specs.py`：验证 17 个算子使用短名
- [x] 4.5 更新集成测试中引用长名的地方（`tests/integration/cleaning/`）
- [x] 4.6 运行 `uv run --group test pytest tests/unit -q` 确认全部通过

## 5. 示例和 Notebook 迁移

- [x] 5.1 更新 `examples/cleaning_runtime.toml` 为新 TOML 结构
- [x] 5.2 搜索替换 `examples/*.py` 中所有长名引用为短名
- [x] 5.3 更新 `notebooks/_helpers/cleaning_configs.py` 中所有长名引用为短名
- [x] 5.4 搜索替换 `notebooks/*.ipynb` 中所有长名引用为短名

## 6. 集成验证

- [x] 6.1 运行 `python -m ruff check src tests` 无新增 lint 错误
- [x] 6.2 运行 `python -m pyright src/image_gallery` 无新增类型错误
- [x] 6.3 运行 `uv run --group test pytest tests/unit -q` 全部通过
- [x] 6.4 运行 `uv run --group test pytest tests/integration -q` 全部通过（如有环境依赖可跳过）
