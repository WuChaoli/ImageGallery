## ADDED Requirements

### Requirement: Tag 定义职责拆分保持协议稳定

系统 SHALL 在把 Tag Definition SQL 拆入私有协作模块后，保持 `DatasetRepo` 的 Tag 公开入口、返回对象、异常文本、Repo 隔离、大小写折叠且不裁剪的名称语义以及每次写入的事务边界不变。

#### Scenario: Tag 写操作经私有协作者执行
- **WHEN** 调用方创建、重命名或归档 Tag Definition
- **THEN** 系统通过私有 Tag 协作者完成单次事务，并保持原返回值、冲突映射、跨 Repo not found 和重复归档行为

#### Scenario: Tag assignment 校验经私有协作者执行
- **WHEN** Dataset Commit 校验一个或多个 tag_id
- **THEN** 系统只接受所属 Repo 的 active Tag，并保持输入去重与既有异常行为
