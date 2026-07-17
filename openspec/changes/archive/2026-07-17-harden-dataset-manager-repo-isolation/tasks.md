## 1. 数据库隔离约束

- [x] 1.1 先增加真实 PostgreSQL 负向测试，证明跨 Repo 的 asset_vectors 与 pending_asset_vectors 组合当前可被错误写入
- [x] 1.2 为 vector_fields 增加 Repo/Field 复合唯一约束，并让两张向量表建立复合外键
- [x] 1.3 更新初始 Alembic migration 与 schema 测试，验证同 Repo 正常写入、跨 Repo 写入被数据库拒绝

## 2. 初始化与资源所有权

- [x] 2.1 先增加全新 PostgreSQL 显式构造测试，复现 ModelManager 在 control schema 创建前绑定失败
- [x] 2.2 调整 DatasetManager 初始化顺序，确保 migration/metadata 初始化先于 ModelManager bind 和 Prefix 恢复
- [x] 2.3 先增加内部、外部共享及重复关闭测试，再实现 `_owns_model_manager` 生命周期规则

## 3. Repo Schema 并发与名称一致性

- [x] 3.1 先增加大小写和首尾空白冲突测试，覆盖普通列到 VectorField 与 VectorField 到普通列两个方向
- [x] 3.2 实现统一 Schema 名称规范键，并让两个 facade 在持锁后重新检查所有普通列和 VectorField
- [x] 3.3 为 PostgreSQL 实现基于 repo_id 稳定 key 的 session advisory lock，并保证异常路径解锁
- [x] 3.4 为 SQLite/local 实现 DatasetManager 实例内按 Repo 的 RLock，保持不同 Repo 独立锁域
- [x] 3.5 增加真实 Backend 并发测试，验证同 Repo 同名修改最多一个成功、不同 Repo 可并行、失败后锁可复用

## 4. 规范与文档收敛

- [x] 4.1 同步 vector-search、repository-vectors、iceberg-datasets、dataset-repositories 与 model-manager 的职责边界
- [x] 4.2 更新受影响 README/AGENTS，明确 ModelManager 所有权、Schema 名称规则和管理员权限 migration 前提
- [x] 4.3 搜索旧 Generation 范围、大小写冲突和资源所有权描述并消除矛盾

## 5. 验证与 PR 收尾

- [x] 5.1 运行聚焦单元测试、真实 PostgreSQL 约束/并发测试、DatasetManager E2E 和演示 Notebook E2E
- [x] 5.2 按顺序运行 format-check、lint、docs、test、coverage、security、package、package-validate、package-smoke 与 test-all
- [x] 5.3 同步主 specs、运行 sync-docs、归档 change 并创建中文提交推送到 PR #10
- [x] 5.4 请求独立代码复审，修复全部 Critical/Important，等待 GitHub 检查全绿后合并 PR #10
