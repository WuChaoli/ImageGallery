## Why

语义去重算子依赖 ONNX Runtime 和 Hugging Face 模型文件，但这些依赖检查仅在 `compute()` 运行时触发。用户配置了 `semantic_duplicate` 后，需要等待前面所有参数节点执行完毕才会得到 "请安装 `image-gallery[semantic]`" 的错误。在 compile/dry-run 阶段提前校验可以秒级反馈，避免无效等待。

## What Changes

- 在 `ParameterComputer` 基类新增 `before_run_check()` 方法，默认空操作
- `SemanticEmbeddingComputer` 和 `SemanticDuplicateGroupComputer` 覆盖该钩子，检查 `onnxruntime`/`faiss-cpu` 可导入性和模型路径可访问性
- `CleaningRuntime` 和 dry-run 流程在运行参数节点前调用 `before_run_check()`
- 依赖缺失时抛出 `SemanticDependencyError`（已有异常类），包含明确的安装指引

## Capabilities

### New Capabilities

_无新增 capability_

### Modified Capabilities

- `cleaning-runtime`: 新增 before_run_check 生命周期钩子调用点，在 compile 和 run 阶段执行前置校验
- `cleaning-operators`: ParameterComputer 基类新增 before_run_check 方法签名

## Impact

- **代码**: `operators/computers/base.py`（基类方法）、`operators/computers/semantic.py`（覆盖实现）、`cleaning/runtime.py`（调用点）、`cleaning/planner.py`（dry-run 调用点）
- **API**: 新增 `ParameterComputer.before_run_check()` 公开方法，向后兼容（默认空操作）
- **依赖**: 无新增依赖
- **测试**: 需新增单元测试覆盖：默认空钩子、semantic 依赖缺失报错、模型路径不存在报错、dry-run 阶段触发校验
