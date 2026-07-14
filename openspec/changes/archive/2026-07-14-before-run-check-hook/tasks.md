## 1. ParameterComputer 基类钩子

- [x] 1.1 在 `src/image_gallery/operators/computers/base.py` 的 `ParameterComputer` 基类新增 `before_run_check(self, config: Mapping[str, object] | None = None) -> None` 方法，默认空操作，添加 Google 风格 docstring
- [x] 1.2 为默认空钩子编写单元测试：实例化一个最小 Computer 子类，调用 `before_run_check()` 不抛异常

## 2. 语义算子 Computer 覆盖钩子

- [x] 2.1 在 `src/image_gallery/operators/computers/semantic.py` 的 `SemanticEmbeddingComputer` 覆盖 `before_run_check()`：try-import `onnxruntime` 和 `huggingface_hub`，失败时抛出 `SemanticDependencyError`（含 `pip install image-gallery[semantic]` 提示）
- [x] 2.2 `SemanticEmbeddingComputer.before_run_check()` 额外检查：若用户通过 config 显式指定了 `model_path`，校验路径存在性，不存在时抛出 `FileNotFoundError`
- [x] 2.3 在 `SemanticDuplicateGroupComputer` 覆盖 `before_run_check()`：复用与 `SemanticEmbeddingComputer` 相同的 `onnxruntime`/`faiss_cpu` 导入检查
- [x] 2.4 编写单元测试：mock `importlib` 使 `onnxruntime` 不可导入，验证 `before_run_check()` 抛出 `SemanticDependencyError`
- [x] 2.5 编写单元测试：验证 `onnxruntime` 可导入时 `before_run_check()` 静默通过

## 3. Scheduler 运行入口集成

- [x] 3.1 在 `src/image_gallery/cleaning/scheduler.py` 的 `ParameterScheduler.run()` 方法中，在进入 `for step in plan.steps` 循环前，收集所有涉及的 `ParameterComputer` 并逐个调用 `before_run_check()`
- [x] 3.2 编写单元测试：构造含参数节点的 `ParameterExecutionPlan`，mock Computer 使 `before_run_check()` 抛错，验证 `scheduler.run()` 在执行任何 `compute()` 前即失败

## 4. Dry-run 诊断入口集成

- [x] 4.1 修改 `src/image_gallery/cleaning/execution.py` 的 `build_dry_run_result()`：新增 `registry: OperatorRegistry | None = None` 参数，当 registry 非 None 时，遍历 graph 中 parameter 类型节点对应的 Computer 调用 `before_run_check()`，捕获异常并追加到 `errors` 列表
- [x] 4.2 更新 `build_dry_run_result()` 的所有调用点，传入 registry（来自 `CleanerExecution.registry`）
- [x] 4.3 编写单元测试：mock Computer 的 `before_run_check()` 抛错，验证 `build_dry_run_result()` 的 `errors` 列表包含该错误信息

## 5. 集成验证

- [x] 5.1 运行 `python -m ruff check src/image_gallery/operators/computers src/image_gallery/cleaning` 无新增 lint 错误
- [x] 5.2 运行 `python -m pyright src/image_gallery` 无新增类型错误
- [x] 5.3 运行 `uv run --group test pytest tests/unit/operators tests/unit/cleaning -q` 全部通过
