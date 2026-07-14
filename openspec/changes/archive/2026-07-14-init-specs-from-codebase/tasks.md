## 1. 验证 spec 文件完整性

- [x] 1.1 确认 13 个 spec 文件均已创建（storage-system, dataset-management, image-import, cleaning-runtime, cleaning-operators, cleaning-config, cleaning-preview, visualization, annotations, utils, reports, config-namespace, state-namespace）
- [x] 1.2 运行 `openspec validate init-specs-from-codebase` 验证变更格式合规
- [x] 1.3 运行 `openspec doctor` 检查关系健康度

## 2. 校验 spec 与代码库一致性

- [x] 2.1 逐个 spec 检查 requirement 中的公开 API 名称与源码匹配
- [x] 2.2 校验 scenario 中的 WHEN/THEN 条件在现有测试中有覆盖
- [x] 2.3 确认 RawDatasetSchema.required_columns 列表与源码一致
- [x] 2.4 确认内置算子目录与 `create_default_registry()` 返回的算子列表一致

## 3. 同步 spec 到主规格目录

- [x] 3.1 运行 `openspec archive init-specs-from-codebase` 将 delta spec 同步到 `openspec/specs/`
- [x] 3.2 运行 `openspec list --specs` 确认 13 个 spec 在主规格目录中可见
- [x] 3.3 运行 `openspec show <spec-name>` 抽查 spec 内容完整

## 4. 收尾验证

- [x] 4.1 运行 `openspec status --change init-specs-from-codebase` 确认变更状态为 complete
- [x] 4.2 确认 `openspec/specs/` 目录下包含 13 个 spec 子目录
- [x] 4.3 提交 git commit：`docs: init openspec specs from codebase`
