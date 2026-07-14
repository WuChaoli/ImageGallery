## MODIFIED Requirements

### Requirement: URL 导入安全边界（PLANNED）
系统 SHALL 在 URL 导入模式下强制执行安全边界检查，拒绝不安全的来源地址。

#### Scenario: 拒绝内网地址
- **WHEN** URL 导入请求指向 localhost、127.0.0.1、10.x.x.x、192.168.x.x 或链路本地地址
- **THEN** 拒绝导入并抛出 SecurityError

#### Scenario: 拒绝云元数据地址
- **WHEN** URL 指向 169.254.169.254（AWS/GCP/Azure 实例元数据）
- **THEN** 拒绝导入并抛出 SecurityError

#### Scenario: 限制重定向
- **WHEN** URL 响应包含重定向且重定向次数超过限制
- **THEN** 中止下载并记录失败

#### Scenario: 限制文件大小
- **WHEN** URL 响应的 Content-Length 超过配置的最大文件大小
- **THEN** 中止下载并记录失败

#### Scenario: 校验 Content-Type
- **WHEN** URL 响应的 Content-Type 不是图片 MIME 类型
- **THEN** 跳过该 URL 并记录在 failure_manifest 中

#### Scenario: 仅允许 HTTP/HTTPS
- **WHEN** URL 的 scheme 不是 http 或 https
- **THEN** 拒绝导入并抛出 ValueError

### Requirement: 导入模式策略（PLANNED）
系统 SHALL 支持三种导入模式，控制图片文件在导入时的物理复制行为。

#### Scenario: copy 模式
- **WHEN** 导入模式为 copy
- **THEN** 将图片文件复制到平台受管存储，image_uri 指向受管存储地址

#### Scenario: reference 模式
- **WHEN** 导入模式为 reference
- **THEN** 仅在 raw Dataset 中登记已有对象的地址，不执行物理复制，image_uri 指向原始地址

#### Scenario: copy_on_write 模式
- **WHEN** 导入模式为 copy_on_write
- **THEN** 初始导入时只登记引用，在清洗或导出需要时才复制到受管存储

#### Scenario: 默认模式为 copy
- **WHEN** 未显式指定导入模式
- **THEN** 使用 copy 模式

#### Scenario: 导入幂等键
- **WHEN** 同一图片被重复导入
- **THEN** 基于 source_uri + image_content_hash + import_run_id 生成幂等键，避免重复写入
