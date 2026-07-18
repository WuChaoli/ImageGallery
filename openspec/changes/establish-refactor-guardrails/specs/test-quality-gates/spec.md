## MODIFIED Requirements

### Requirement: 覆盖率必须同时防止全仓回退和未测试变更

系统 SHALL 使用默认快速测试测量 `src/image_gallery` 覆盖率。全仓源码行覆盖率 MUST 不低于 90.00%，PR 新增或修改的可执行行 diff coverage MUST 不低于 80%。

#### Scenario: PR 新增逻辑缺少测试
- **WHEN** PR 新增可执行业务逻辑且 diff coverage 低于 80%
- **THEN** 覆盖率检查失败并阻止合并

#### Scenario: 文档变更没有可执行行
- **WHEN** PR 仅修改文档或其他无 coverage 信息的文件
- **THEN** diff coverage 检查成功而不是报错

#### Scenario: 全仓覆盖率低于明确底线
- **WHEN** 默认快速测试产生的全仓源码行覆盖率低于 90.00%
- **THEN** 覆盖率检查失败，即使 diff coverage 达到 80%

#### Scenario: 全仓覆盖率达到明确底线
- **WHEN** 默认快速测试产生的全仓源码行覆盖率达到或高于 90.00% 且 diff coverage 达到 80%
- **THEN** 双层覆盖率检查成功

## ADDED Requirements

### Requirement: 重构必须执行公开接口契约回归

系统 SHALL 通过默认快速测试冻结公开包导出、可检查的公开调用签名以及 OpenSpec 明确承诺的关键隔离语义。内部私有模块与私有符号不属于稳定接口，MUST NOT 因契约测试而被强制保留。

#### Scenario: 重构修改公开导出
- **WHEN** 重构删除、重命名或新增包级 `__all__` 导出但未形成明确的产品行为变更
- **THEN** 公开接口契约测试失败并阻止合并

#### Scenario: 重构修改公开签名
- **WHEN** 重构改变已导出函数、类或方法的可检查调用签名
- **THEN** 公开接口契约测试失败并指出发生漂移的符号

#### Scenario: 重构移动私有实现
- **WHEN** 重构仅移动或拆分未公开的内部模块、私有函数或私有类且公开契约保持一致
- **THEN** 公开接口契约测试继续成功

#### Scenario: Cleaning 惰性导入保持语义
- **WHEN** 调用方访问 `image_gallery.cleaning` 的任一公开惰性导出或未知名称
- **THEN** 公开导出解析为原对象，未知名称继续抛出 `AttributeError`
