# TLM 架构设计与技术栈规划

## 1. 项目定位

TLM 当前定位为本地优先的 Test Login Manager，用于帮助测试人员管理业务系统、角色账号、账号占用状态，并通过本机 Chrome 快速打开登录页和自动填充账号密码。

它目前不是完整自动化测试平台，而是未来自动化测试平台之前的登录与账号管理底座。

当前核心目标：

- 管理测试系统、角色账号和账号占用状态。
- 减少测试人员重复登录成本。
- 支持普通页签、访客模式、无痕模式、Chrome 个人资料等浏览器上下文。
- 通过 Playwright 控制本机 Chrome 自动填充账号密码。
- 遇到验证码时交给人工处理。
- 保持清晰边界，为后续平台化和自动化测试执行能力预留扩展空间。

## 2. 当前架构现状

```text
浏览器 UI
  -> 本地 Python HTTP API :7070
    -> SQLite
    -> Playwright Adapter
      -> 本机 Chrome
```

当前模块分层：

```text
backend/app/main.py
  路由、静态文件服务、JSON 响应

backend/app/services.py
  业务规则、账号状态、会话状态、校验逻辑

backend/app/repositories.py
  SQLite 数据访问

backend/app/database.py
  Schema 初始化、迁移补丁、Seed 数据

backend/app/playwright_adapter.py
  Playwright 控制本机 Chrome、自动填充、会话生命周期回写

backend/app/browser_launcher.py
  原生方式打开本机 Chrome 登录页

backend/app/security.py
  密码加解密边界

frontend/index.html
frontend/src/api.js
frontend/src/app.js
frontend/src/styles.css
  原生 Web 前端、状态渲染、接口调用、填充状态轮询
```

## 3. 当前技术栈

### 前端

```text
HTML + CSS + 原生 JavaScript
```

优点：

- 无构建工具，启动和部署简单。
- 适合本地工具 MVP。
- 可直接由 Python 后端静态托管。

不足：

- `frontend/src/app.js` 会随着状态、弹窗、轮询、表单逻辑增加而变重。
- 缺少组件化和类型约束。
- 后续加入任务队列、执行报告、权限体系后维护成本会上升。

### 后端

```text
Python 标准库 http.server
SQLite
Playwright
```

优点：

- 依赖少，适合本地运行。
- Python 生态适合后续接 Playwright、自动化脚本和数据处理。
- 服务层、数据层、浏览器 Adapter 已经有较清晰边界。

不足：

- `http.server` 不适合云端多人使用。
- SQLite 不适合多人并发、审计和复杂查询。
- Playwright 执行和 API 服务在同一进程，长期需要拆分。
- 密码加密仍是开发级边界，不适合保存真实生产级凭据。

## 4. 已完成的重要架构能力

### 4.1 本机 Chrome 执行

填充流程已从 Playwright 默认浏览器改为显式使用用户本机 Chrome 可执行文件。

这保证了自动填充时使用的是本机安装的 Chrome binary，而不是 Playwright 下载的 Chromium。

需要注意：

- 这不等于接管用户已经打开的日常 Chrome 窗口。
- Playwright 自动填充仍需要启动一个受控 Chrome 实例。
- 如果回退到原生 Chrome 打开页面，则只能打开页面，不能自动填写密码。

### 4.2 Profile Fallback

当使用 Chrome 个人资料发生冲突或连接中断时，系统会自动回退到原生方式打开目标登录页。

回退模式能力边界：

- 可以帮用户打开登录页面。
- 不能自动填写密码。
- 不能可靠监听用户何时关闭原生 Chrome 页面。
- 需要用户手动释放账号占用状态。

### 4.3 会话状态机

当前浏览器会话已从简单 `active/released` 演进为更细状态：

```text
starting
filling
ready
fallback
failed
released
```

状态含义：

```text
starting  已创建会话，正在准备启动浏览器
filling   正在打开 Chrome 并定位登录页
ready     填充流程完成，页面仍处于使用中
fallback  已回退为原生 Chrome 打开页面，需要手动登录
failed    填充失败，账号已自动释放
released  会话释放，账号回到空闲
```

前端已基于 `session_id` 轮询会话状态，并在 ready、fallback、failed、released 时刷新账号、访客会话数和日志。

### 4.4 失败自动释放

当 Playwright 线程启动失败、页面导航失败或填充异常时，系统会：

- 将 `browser_sessions.status` 标记为 `failed`。
- 写入失败 message。
- 将账号状态恢复为 `idle`。
- 写入操作日志。

这避免了失败后账号长期停留在“使用中”的问题。

## 5. 云服务器部署阻碍

直接部署到云服务器可以运行 UI、API 和数据库，但浏览器辅助登录能力会发生本质变化。

主要阻碍：

### 5.1 云端无法使用用户本机 Chrome

当前项目的核心能力依赖本机 Chrome。

部署到云服务器后，Playwright 控制的是服务器上的 Chrome，而不是测试人员电脑上的 Chrome。

因此无法使用：

- 用户本机 Chrome profile。
- 用户本机 cookie。
- 用户本机插件。
- 用户本机密码管理器。
- 用户已有登录态。

### 5.2 Chrome Profile 语义会改变

云端读取到的是服务器上的 Chrome profile，而不是访问者自己的 Chrome profile。

所以“选择个人资料”在云端部署后不再符合当前产品语义。

### 5.3 云服务器通常没有桌面环境

当前使用 `headless=False` 打开可见 Chrome。

普通 Linux 云服务器没有图形桌面，需要额外配置：

- Xvfb
- VNC/noVNC
- 远程桌面
- Browserless 类远程浏览器服务

否则用户无法看到验证码页面，也无法人工接管。

### 5.4 验证码交互不自然

当前产品设计把验证码留给人工输入。

云端执行时，验证码页面打开在服务器浏览器里，用户无法直接看到或操作。

要解决这个问题，需要：

- 测试环境关闭验证码。
- 提供验证码 bypass。
- 接入短信/图形验证码 mock。
- 提供远程浏览器画面和交互通道。

### 5.5 当前服务只适合本机访问

当前后端绑定：

```python
HOST = "127.0.0.1"
PORT = 7070
```

云部署需要改为：

```python
HOST = "0.0.0.0"
```

并放在 Nginx、HTTPS、防火墙和鉴权之后。

### 5.6 缺少用户登录和权限体系

当前系统默认运行在本地可信环境。

云端暴露后必须补齐：

- 用户登录。
- 角色权限。
- 系统/账号访问控制。
- 操作审计。
- 敏感操作确认。

### 5.7 密码存储不适合云端

当前 `security.py` 是开发期加密边界，不是生产级凭据管理方案。

云端必须改为：

- KMS。
- Vault。
- 云密钥服务。
- macOS Keychain / Windows Credential Manager。
- 或至少 AES-GCM/Fernet 级别加密和密钥轮换。

### 5.8 SQLite 不适合多人云端并发

SQLite 适合本地工具和低并发。

如果作为团队共享平台，需要迁移到：

- PostgreSQL。
- MySQL。

## 6. 自动化测试平台与当前项目的关系

两者底层原理相同：都使用浏览器自动化驱动页面。

但目标不同。

### 当前 TLM

```text
测试人员本机
  -> 选择系统和账号
  -> 打开自己的 Chrome 或指定浏览器模式
  -> 自动填账号密码
  -> 人工处理验证码
  -> 管理账号占用
```

目标是辅助人工快速进入测试状态。

### 自动化测试平台

```text
测试平台 / CI / 执行节点
  -> 启动受控浏览器
  -> 使用托管测试账号
  -> 执行固定脚本
  -> 生成截图、日志、Trace、报告
```

目标是稳定、可重复、隔离、可无人值守。

关键差异：

- 浏览器在哪里执行。
- 是否复用用户本机 profile。
- 是否依赖人工验证码。
- 账号是否由平台托管。
- 是否需要可重复脚本和断言。
- 是否需要执行报告和失败诊断。

## 7. 推荐演进路线

### 阶段一：继续强化本地工具

目标：

- 保持本地运行。
- 强化账号占用生命周期。
- 提升本机 Chrome 填充稳定性。
- 明确普通打开和自动填充的能力边界。

建议技术形态：

```text
Desktop Web UI
  -> Local Python API
    -> SQLite
    -> Local Browser Adapter
      -> User Chrome
```

重点任务：

- 完善会话状态机。
- 增加失败截图和错误日志。
- 增加每个系统自定义选择器。
- 增加自动释放超时策略。
- 增加 Chrome/Playwright 可用性检查。
- 更新 ARCHITECTURE.md，使文档与当前代码一致。

### 阶段二：团队共享账号池

目标：

- 账号目录、状态和日志集中管理。
- 浏览器执行仍保留在用户本机 Agent。
- 云端不直接接管用户 Chrome。

推荐架构：

```text
Web UI
  -> Platform API
    -> PostgreSQL
    -> Credential Store
    -> Audit Log

Local Agent
  -> User Chrome
  -> 回传执行状态
```

推荐技术栈：

```text
FastAPI
PostgreSQL
Redis 或轻量任务队列
Local Agent
Vault/KMS/Keychain
React/Vue/Svelte 或继续轻量前端
```

重点任务：

- 用户登录和权限。
- 系统/账号级访问控制。
- Local Agent 注册和心跳。
- 云端下发填充任务，本地 Agent 执行。
- 账号状态由 Agent 回报闭环。
- 凭据密钥管理。

### 阶段三：自动化测试执行平台

目标：

- 支持无人值守自动化测试。
- 支持远程浏览器执行。
- 支持截图、Trace、日志、报告。
- 支持任务调度和执行节点扩展。

推荐架构：

```text
Web UI
  -> Platform API
    -> PostgreSQL
    -> Redis Queue
    -> Object Storage
    -> Secret Manager

Execution Workers
  -> Playwright / Chrome
  -> Screenshots
  -> Traces
  -> Reports
```

推荐技术栈：

```text
FastAPI 或 NestJS
PostgreSQL
Redis + Celery/RQ
Playwright Test
Dockerized browser workers
S3/MinIO
OpenTelemetry
RBAC
Nginx + HTTPS
```

重点任务：

- 测试用例模型。
- 登录脚本模型。
- 系统级自定义选择器。
- 执行队列。
- Worker 注册与调度。
- 测试报告和失败诊断。
- Trace Viewer 集成。
- 环境隔离和账号池调度。

## 8. 推荐的近期技术改造优先级

### P0：同步文档和当前代码

当前 `ARCHITECTURE.md` 仍描述早期 stub 状态，应更新为真实 Playwright、本机 Chrome、会话状态轮询后的架构。

### P1：浏览器执行稳定性

- 为每个系统配置用户名、密码、验证码选择器。
- 填充失败时保存截图。
- 记录 Playwright 失败原因。
- 增加 Chrome 可执行文件检测接口。
- 增加浏览器模式能力说明。

### P1：账号状态闭环

- 自动释放超时。
- fallback 会话的手动释放提醒。
- 长时间 active 会话告警。
- 页面关闭、失败、手动释放的日志统一。

### P2：后端框架迁移

从 `http.server` 迁移到 FastAPI。

收益：

- 路由清晰。
- 自动 OpenAPI 文档。
- 更好的错误处理。
- 更容易加鉴权。
- 更容易接后台任务和 WebSocket。

### P2：前端模块化

短期可以继续原生 JS，但建议拆分：

```text
state.js
api.js
renderSystems.js
renderAccounts.js
dialogs.js
sessionPolling.js
```

如果继续扩展到平台形态，再考虑 React/Vue/Svelte。

### P2：凭据安全升级

本地版本：

- macOS Keychain。
- Windows Credential Manager。

平台版本：

- Vault。
- KMS。
- AES-GCM/Fernet + 密钥轮换。

### P3：数据库迁移

当出现多人共享、云部署、复杂审计时，从 SQLite 迁移到 PostgreSQL。

## 9. 关键架构判断

当前技术栈适合做本地登录管理器 MVP。

如果目标仍是“测试人员本机辅助登录”，不要急着云端化浏览器执行；应该优先强化本地 Agent 能力。

如果目标是“团队共享账号池”，云端应该负责账号、权限、审计和任务下发，本机 Agent 负责 Chrome 控制。

如果目标是“自动化测试平台”，就要接受浏览器运行在执行节点上，测试账号由平台托管，验证码需要测试环境旁路或专门处理。

最重要的拆分方向：

```text
API 服务
账号与会话状态
浏览器执行器
```

这三者拆清楚后，项目既可以继续保持本地工具形态，也可以自然演进为云端平台和远程自动化执行系统。
