# 更新日志

版本说明与 `assets/changelog.json` 同步；应用内「更新公告」亦读取该文件。

## 1.2.3（2026-06-10）

**微信桥接加固、文件安全、状态栏检测与 API 稳定性**

### 新功能

- 内置「文件删改安全」准则（skill + 规则 + 插件）：删/改/移须专用工具并审批，禁止 Python/PowerShell 绕过
- `run_python` 静态安全分析（`python_code_safety`）：拦截改 AppData/星期五配置；删除/覆盖每次审批，工作区新建同轮确认一次
- API 凭据独立存储（`credentials_store`），与 settings 分离，换机/更新更稳
- 开机 API 检测与设置页「测试连接」统一逻辑（`startup-tests` + `test_*_service`）
- 状态栏三项（API / 视觉 / 生图）独立并行检测，谁先完成谁先更新
- 微信登录运行器（`login_runner`）与资料同步（`profile`），Gateway 插件单 hook 去重
- 审批说明文案外置（`approval_descriptions`），工具审批弹窗更清晰
- `server` 拆出 `status_bar`、`weixin_routes`；设置页拆 weixin / python_env 面板脚本
- 打包脚本 `pack-windows.cmd` / `pack-windows.ps1`

### 改进

- 微信桥接：去掉 `inbound_claim` 双转发；`forwardToFridayOnce` 去重；`before_dispatch` 620s 超时防慢回复
- 微信问候快路径（你好等）在 API 就绪时直接回复，减少空等
- 状态栏开机默认「检测中」黄点，不再先显示关/离线；检测完成前轮询不覆盖结果
- 测试连接成功不再清空其他服务状态缓存，避免生图测完后视觉/API 被重复检测
- API 瞬态超时/限流不误标永久离线；`brain` 对瞬态失败自动重试
- 生图状态栏：有成功缓存时跳过重复 live probe；快速探测不覆盖成功缓存
- 交互规则：允许正常闲聊，不必强行拉回电脑管理话题
- Python Agent 环境：修复误绑开发目录 venv、跨机重建与设置页后台安装进度
- 可移植性/配置包：credentials 合并、插件 manifest 与内置 file-safety 一并迁移
- Yolo 模式下 `run_python` / PowerShell 仍须每次审批
- 扩展管理 UI 与 onboarding 流程优化

### 修复

- 用着用着误报「无法连接 API」、设置里测试却正常（响应超时与缓存污染）
- 状态栏 API/视觉/生图与设置页测试结果不一致
- `run_python` 未审批即可删改 `operations.json` 等应用数据
- 微信英文错答、重复回复、审批/通道与 Gateway 插件 inflight 问题
- 生图离线误报、设置测试通过但底部仍显示离线
- `category_profiles` / `llm_profiles` 切换生图与 API 快照恢复
- registry 工具导入与若干微信/setup 边界用例

### 测试

- 新增/扩充：`api_connect`、`status_bar`、`startup_tests`、`python_code_safety`、`credentials_store`、weixin bridge/login/profile/node_runtime 等测试

---

## 1.2.2（2026-06-09）

**微信桥接、设置持久化与生图测试修复**

### 改进

- 状态栏常驻显示缓存命中百分比
- 微信「我的微信」会话启动预建与 WebSocket 实时刷新侧边栏
- 设置页 Python 环境 / 生图测试改为后台执行，不再卡死整个后端

### 修复

- 更新后 API Key 丢失：自动迁移 Friday-Test 与 `.fernet_key` 配对
- 生图设置测试超时无反馈、中转站探测过久
- Agent Python 环境误绑开发目录 venv 导致更新后需重装

---

## 1.2.1（2026-06-09）

**Plan/Todo 完整版与 API 连接修复**

### 改进

- Plan / 待办面板恢复 1.2.1 完整 UI：拖拽排序、待办队列、从计划生成、进度徽章
- 长任务待办自动勾选、计划 Markdown 同步、对话中实时刷新面板
- 设置页空 base_url 自动回退 DeepSeek 默认地址，修复 API 测试 Connection error

### 修复

- 源码回退后待办面板与版本号与安装包不一致的问题

---

## 1.2.0（2026-06-08）

**缓存优化、变更审查、Plan/MCP 与自启完善**

### 新功能

- DeepSeek 前缀缓存：冻结 system/tools、append-only 上下文折叠、状态栏 cache 命中率
- Agent 写文件后在聊天区展示 diff 摘要，支持在资源管理器中打开
- 会话 Plan / Todo 面板与 `update_session_plan` / `update_session_todos` 工具
- MCP stdio 客户端：设置 → 扩展 → MCP，配置随配置包 portable 迁移
- OpenClaw Gateway 开机自启开关（设置 → 微信端 AI）
- 星期五本体开机自启（设置 → 启动）

### 改进

- 工具输出智能压缩、重复工具循环检测、前缀漂移日志
- 配置包导出/导入包含 `mcp_servers.json`
- 内置技能「制定计划」

## 1.1.3（2026-06-08）

**可移植性迁移、对话体验与 UI 抛光**

### 新功能

- 设置 → 日志：配置包导出/导入（zip），换机迁移设置、技能、规则、插件与加密密钥
- 可移植性自检：工作区、API Key 加密、插件 manifest、Agent Python 环境
- 助手回复支持一键复制与引用到输入框
- workspace 支持 `~/`、`%VAR%`、`auto`；settings 自动 schema 迁移
- 安全设置新增「只读访问桌面/文档/下载等用户文件夹」

### 改进

- 插件 manifest 磁盘保留 `{plugin_dir}`，运行时替换；启动一次性迁移旧绝对路径
- 会话生图路径相对化，整夹迁移后历史图片仍可显示
- PowerShell / Python 子进程 UTF-8 输出链路补全
- 无效 workspace、生图目录、加密密钥未配对时启动自愈并提示
- UI 抛光：历史抽屉避让标题栏、Composer 停止/发送并排、复制/引用置于回复末尾
- 启动加速：路径/插件 manifest 迁移完成后跳过重复全量扫描

### 修复

- 修复配置包导入缺少 python-multipart 导致后端无法启动、应用打不开
- 修复 workspace 指向其他用户或无效盘符时无法使用
- Agent Python 虚拟环境跨机拷贝后失效检测与重建引导

---

## 1.1.2（2026-06-07）

**Win10 零门槛安装：运行组件自动补齐**

### 新功能

- 首次启动自动检测并安装 WebView2、VC++ 运行库（Win10 白屏/缺 DLL 常见修复）
- 新增「首次安装.ps1」：一键解除锁定、创建快捷方式并启动
- Agent Python 环境支持自动 winget / 便携 Python 下载，无需手动装 Python
- 微信端 AI 一条龙：自动安装 Node/OpenClaw、扫码登录、长超时与桥接修复

### 改进

- 安装包打包阶段自动 Unblock，减少 Zone.Identifier 导致的 pythonnet 错误
- 安装教程更新为零门槛 3 步流程

---

## 1.1.1（2026-06-07）

**打包修复：跨机运行与 API 测试**

### 修复

- 修复其他电脑运行 exe 时 pythonnet / Python.Runtime 初始化失败
- 安装包目录改为英文 `Friday`，避免中文路径导致 DLL 加载失败
- 修复首次向导测试 API 时误报「网络错误」
- 打包版补充 HTTPS 证书链，修复 DeepSeek API 测试连接失败
- 修复 Gitee Release 名称中文乱码

### 改进

- 安装教程补充 .NET / WebView2 / API 测试排错说明

---

## 1.1.0（2026-06-07）

**生图持久化、桌面体验与更新公告**

### 新功能

- 生图结果写入会话历史，重新打开对话仍可查看已生成图片
- 内置更新公告：启动时展示未读版本说明，设置页可查看完整更新历史
- 微信端 AI 桥接向导（OpenClaw 一键配置）

### 改进

- 桌面窗口启动流程优化，减少黑屏闪烁
- Win11 风格无边框标题栏，去除最小化按钮周围黑色焦点框
- 生图 API 支持 OpenAI 兼容中转与火山方舟，可配置备用端点

### 修复

- 修复会话刷新后生图附件丢失的问题
- 修复微信 Bot User-Agent 版本号未随应用更新同步的问题

---

## 1.0.4（2026-05-01）

**稳定版维护**

### 改进

- 更新检查优先使用 Gitee Releases（国内免 VPN）
- 设置页安全策略与定时任务体验优化
