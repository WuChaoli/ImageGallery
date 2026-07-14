## 1. 增补 spec 到主规格

- [x] 1.1 将 semantic-duplicate-operator spec archive 到 `openspec/specs/semantic-duplicate-operator/`
- [x] 1.2 将 notebook-infrastructure spec archive 到 `openspec/specs/notebook-infrastructure/`
- [x] 1.3 将 dataset-management spec 的 I/O 可插拔模型场景 archive 到 `openspec/specs/dataset-management/`
- [x] 1.4 将 image-import spec 的元数据扩展字段和路径分片场景 archive 到 `openspec/specs/image-import/`
- [x] 1.5 将 cleaning-preview spec 的逐算子预览场景 archive 到 `openspec/specs/cleaning-preview/`

## 2. 验证

- [x] 2.1 运行 `openspec validate complete-superpowers-gaps` 确认格式合规
- [x] 2.2 运行 `openspec list --specs` 确认总 spec 数从 17 增长到 19
- [x] 2.3 确认 image-import、dataset-management、cleaning-preview 的 requirements 数量增长

## 3. 收尾

- [x] 3.1 提交 git commit：`docs: complete superpowers spec gaps in openspec`
