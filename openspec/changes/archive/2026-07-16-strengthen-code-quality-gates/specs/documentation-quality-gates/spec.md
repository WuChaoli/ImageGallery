## ADDED Requirements

### Requirement: Markdown 只阻断确定性结构错误

系统 SHALL 检查标题层级、列表缩进、围栏闭合、文件尾换行、重复锚点和链接语法。系统 MUST NOT 强制固定行宽、自动重排表格、转换中文标点或要求所有代码块声明语言。

#### Scenario: Markdown 围栏未关闭
- **WHEN** PR 引入未闭合的 fenced code block
- **THEN** 文档质量检查失败

#### Scenario: 中文文档使用全角标点
- **WHEN** 中文文档或 docstring 使用符合中文表达的全角标点
- **THEN** 文档门禁不因标点未转换为半角而失败

### Requirement: 内部链接与外部链接必须分层检查

仓库内部相对链接失效 MUST 阻断 PR；外部 HTTP 链接 SHALL 在定时任务中检查并报告，MUST NOT 因临时网络、限流或地区访问问题阻断普通 PR。

#### Scenario: PR 删除被 README 引用的文件
- **WHEN** README 中的相对链接指向不存在的仓库文件
- **THEN** 文档质量检查失败

#### Scenario: 外部网站暂时超时
- **WHEN** 定时链接检查访问外部网站超时
- **THEN** 任务报告该链接但不改变普通 PR required checks

### Requirement: 英文拼写检查必须使用项目词典

系统 SHALL 对英文技术文本执行高确定性拼写检查，并 SHALL 维护 ImageGallery、MinIO、Pyright、LabelImg、fastdup、CleanVision、`image_uri` 和 `source_uri` 等项目词汇。系统 MUST NOT 尝试对中文自然语言执行语法审查。

#### Scenario: 英文错误消息拼写错误
- **WHEN** PR 在错误消息或英文文档中引入高确定性拼写错误
- **THEN** 拼写检查失败并提供候选修正

### Requirement: OpenSpec 必须严格校验

活动 change SHALL 通过 `openspec validate --strict`。系统 MUST NOT 仅因 `src/` 变化就机械要求修改 OpenSpec，但产品行为变化 MUST 具有已确认的活动 change。

#### Scenario: delta spec 场景格式无效
- **WHEN** 活动 change 的 requirement 或 scenario 不符合 OpenSpec 严格格式
- **THEN** 文档治理检查失败

#### Scenario: 纯格式化代码
- **WHEN** PR 只机械格式化代码且不改变产品行为
- **THEN** 系统不要求创建虚假的产品行为 spec
