## 1. 依赖准备

- [x] 1.1 在 `pyproject.toml` 的 `dependencies` 中新增 `pyyaml>=6.0`
- [x] 1.2 运行 `uv sync` 安装 pyyaml

## 2. ActionRange 区间解析器

- [x] 2.1 新建 `src/image_gallery/cleaning/action_range.py`：实现 `ActionRange` dataclass（lower, upper, lower_inclusive, upper_inclusive），`from_string()` 类方法解析区间语法，`contains(value)` 方法判断值是否在区间内
- [x] 2.2 实现区间类型校验：闭区间 `[]`、开区间 `()`、混合 `(]`/`[)`，拒绝无穷、拒绝无括号语法
- [x] 2.3 新建 `tests/unit/cleaning/test_action_range.py`：覆盖闭区间、左开右闭、右开左闭、contains 边界值、无效语法报错、无穷报错

## 3. MetricSpec 指标元数据

- [x] 3.1 新建 `src/image_gallery/operators/metric_spec.py`：实现 `MetricSpec` dataclass（name, value_type, direction, absolute_min, absolute_max），`relative_to_absolute()` 函数
- [x] 3.2 在 `builtin.py` 中为 17 个内置算子定义 MetricSpec 注册表（`create_default_metric_specs()` 函数）
- [x] 3.3 新建 `tests/unit/operators/test_metric_spec.py`：覆盖 absolute/relative/categorical 三种类型、relative_to_absolute 映射和越界报错

## 4. CleanerRecipe YAML 配方

- [x] 4.1 新建 `src/image_gallery/cleaning/recipe.py`：实现 `CleanerRecipe` dataclass（version, run_defaults, operators），`from_yaml()` 类方法加载 YAML 文件
- [x] 4.2 实现 `compile_selectors()` 方法：将 YAML operators 列表编译为 `select_operators()` 可消费的 selector 列表（支持 rules 区间、绝对阈值、布尔 action 三种模式）
- [x] 4.3 实现 `BasicCleaner.from_recipe(yaml_path)` 工厂方法：解析 YAML → 编译 selector → 构造 BasicCleaner
- [x] 4.4 新建 `tests/unit/cleaning/test_recipe.py`：覆盖 from_yaml 加载、compile_selectors 三种算子模式、from_recipe 工厂、version 校验、空 operators 报错

## 5. 双级动作评估

- [x] 5.1 在 `src/image_gallery/cleaning/recipe.py` 或新建 `src/image_gallery/cleaning/rule_evaluator.py`：实现 `evaluate_with_rules()` 函数，接受 parameter_table、MetricSpec 和 ActionRange 规则，按 drop > review > keep 优先级输出 action 列
- [x] 5.2 编写单元测试：覆盖相对指标区间评估、绝对指标阈值评估、drop 优先于 review 的优先级

## 6. RunStore 存储模式

- [x] 6.1 新建 `src/image_gallery/cleaning/run_store.py`：定义 `RunStore` Protocol（write_table/read_table/write_json/read_json/materialize_dataset/cleanup）
- [x] 6.2 实现 `MemoryRunStore`：字典存储，无文件 IO，cleanup 清空字典
- [x] 6.3 实现 `TemporaryRunStore`：使用 `tempfile.mkdtemp()`，cleanup 时 `shutil.rmtree`
- [x] 6.4 实现 `DiskRunStore`：封装现有 `cache_root / run_id` 路径逻辑
- [x] 6.5 修改 `CleaningRuntime`：接受可选 `run_store: RunStore` 参数，缺省使用 DiskRunStore
- [x] 6.6 新建 `tests/unit/cleaning/test_run_store.py`：覆盖三种模式的 write/read/cleanup 行为

## 7. 集成验证

- [x] 7.1 运行 `python -m ruff check src/image_gallery/cleaning/action_range.py src/image_gallery/cleaning/recipe.py src/image_gallery/operators/metric_spec.py src/image_gallery/cleaning/run_store.py` 无 lint 错误
- [x] 7.2 运行 `python -m pyright src/image_gallery` 无新增类型错误
- [x] 7.3 运行 `uv run --group test pytest tests/unit/cleaning tests/unit/operators -q` 全部通过
