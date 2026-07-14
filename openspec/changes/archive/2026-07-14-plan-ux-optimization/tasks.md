## 1. 增补 spec 到主规格

- [ ] 1.1 将 cleaning-operators spec 的短名命名和用户规则元数据场景 archive 到 `openspec/specs/cleaning-operators/`
- [ ] 1.2 将 cleaning-config spec 的 YAML Recipe、ActionRange、MetricSpec、双级评估场景 archive 到 `openspec/specs/cleaning-config/`
- [ ] 1.3 将 cleaning-runtime spec 的非阻塞运行、协作式停止、RunProgress、RunStore、before_run_check 场景 archive 到 `openspec/specs/cleaning-runtime/`
- [ ] 1.4 将 cleaning-preview spec 的 export("ALL") 和导出默认列契约场景 archive 到 `openspec/specs/cleaning-preview/`

## 2. 验证

- [ ] 2.1 运行 `openspec validate plan-ux-optimization` 确认格式合规
- [ ] 2.2 运行 `openspec list --specs` 确认 4 个 spec 的 requirements 数量增长

## 3. 收尾

- [ ] 3.1 提交 git commit：`docs: add UX optimization plan specs to openspec`
