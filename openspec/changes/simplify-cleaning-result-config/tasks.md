## 1. Characterization Tests

- [x] 1.1 补充 Result 缺失产物回退、状态、结果和解释语义测试
- [x] 1.2 补充 Result 导出、debug bundle 与清理边界测试
- [x] 1.3 补充 operator HTML 预览过滤、排序、数量覆盖和错误语义测试
- [x] 1.4 补充 TOML/YAML 配置选择、模板往返和嵌套 policy 校验测试
- [x] 1.5 通过受控 mutation 验证新增 characterization tests 会在语义漂移时失败

## 2. Result Simplification

- [x] 2.1 提取运行产物路径、表、manifest、relation 与状态读取的私有对象
- [x] 2.2 提取 table、manifest、relation 和 debug bundle 文件导出私有函数
- [x] 2.3 提取 operator preview frame、过滤、排序与 options 准备私有函数
- [x] 2.4 将 `CleanerResult` 收敛为稳定公开门面并保持返回与异常语义

## 3. Config Simplification

- [x] 3.1 提取 TOML 模板渲染与值格式化私有模块
- [x] 3.2 提取 `NodePolicy` 及嵌套 policy 解析与类型校验私有模块
- [x] 3.3 简化 `CleanerConfig` 与 `CleanerRecipe` 入口并保持选择、编译和错误语义

## 4. Verification

- [x] 4.1 运行 Result/config/preview/export/recipe 目标测试并确认零失败
- [x] 4.2 运行 format-check、lint、docs、默认 test 和 OpenSpec strict validate
- [x] 4.3 验证 source coverage 不低于 90%，diff coverage 不低于 80%
- [x] 4.4 审查公开导出、公开签名、返回值、异常文本和持久化格式均未改变
