## 1. 增补 spec 到主规格

- [ ] 1.1 将 image-import spec 的 URL 安全边界和导入模式场景 archive 到 `openspec/specs/image-import/`
- [ ] 1.2 将 cleaning-runtime spec 的核心不变量场景 archive 到 `openspec/specs/cleaning-runtime/`
- [ ] 1.3 将 storage-system spec 的受管路径安全约束场景 archive 到 `openspec/specs/storage-system/`

## 2. 验证

- [ ] 2.1 运行 `openspec validate digest-docs-design-decisions` 确认格式合规
- [ ] 2.2 运行 `openspec list --specs` 确认 3 个 spec 的 requirements 数量增长

## 3. 标记 docs/ 状态

- [ ] 3.1 在 AGENTS.md 中添加 docs/ 文档状态索引，标记 V1/V2 旧设计为"已被 superseded"
- [ ] 3.2 提交 git commit：`docs: digest design decisions from docs into openspec specs`
