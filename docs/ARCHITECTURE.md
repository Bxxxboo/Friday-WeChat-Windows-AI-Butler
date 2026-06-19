# 星期五 · 源码架构

本文档描述仓库目录职责与模块边界，便于新人快速定位代码。  
**运行时入口不变**：`run.py` → `friday.desktop.main()` → `friday.server:app`。

## 顶层目录

```
E:\Friday\
├── run.py              # 单实例检查 + 启动桌面壳
├── setup.ps1           # 创建 .python-env 并安装依赖
├── friday/             # Python 后端（见下）
├── web/                # 前端 SPA（Vanilla JS）
├── tests/              # pytest，按域分子目录
├── scripts/            # 构建 / 发布 / 安装 / 诊断
├── release/            # 用户 zip 附件（教程、快捷方式）
├── docs/               # 维护者文档
├── extensions/         # 内置插件包（打包进 exe）
└── assets/             # changelog.json、图标等
```

| 目录 | 职责 |
|------|------|
| `friday/` | Agent、API、工具、微信桥、Windows 集成 |
| `web/` | 对话 UI、设置页、onboarding |
| `scripts/` | 不随应用分发；开发/CI 用 |
| `release/` | 随 `Friday-Windows.zip` 分发给用户 |
| `extensions/` | OpenClaw 插件 manifest + SKILL 文本 |

## `friday/` 包结构

子包仅三处：`api/`、`tools/`、`weixin/`。其余模块在包根，按领域分组如下。

### 入口与桌面

| 模块 | 说明 |
|------|------|
| `desktop.py` | pywebview 窗口、uvicorn 线程 |
| `server.py` | FastAPI 装配：lifespan、token 中间件、`register_*_routes`（~180 行） |
| `api/routes/` | 按域拆分的路由（settings、sessions、chat、plugins、diagnostics、static） |
| `api/weixin_routes.py` | 微信桥 REST |
| `api/chat_runtime.py` | WebSocket 聊天运行时、Agent 缓存与审批状态 |
| `api/schemas.py` | HTTP 请求/响应 Pydantic 模型 |
| `splash.py` | 启动页 HTML |
| `single_instance.py` / `instance_lock.py` | 防多开 |
| `edition.py` | AppData 名、默认端口 |
| `win32_chrome.py` / `win10_runtime.py` | 无边框窗、WebView2 依赖 |

### Agent 与 LLM

| 模块 | 说明 |
|------|------|
| `agent.py` | 工具循环、审批、取消 |
| `brain.py` | DeepSeek 调用、系统 prompt |
| `context.py` | 工具结果压缩 |
| `prefix_cache.py` | 前缀缓存 |
| `interaction_modes.py` | Ask / Agent / Yolo |
| `safety.py` | 风险分级与审批策略 |

### 配置与服务商

| 模块 | 说明 |
|------|------|
| `storage.py` | settings.json + Key 加密 |
| `paths.py` | AppData、web 目录 |
| `model_providers.py` | 大模型预设目录 |
| `llm_profiles.py` | 按服务商记忆 Key/模型 |
| `category_profiles.py` | 视觉/生图配置记忆 |
| `custom_endpoints.py` | 自定义 OpenAI 兼容端点 |
| `vision.py` / `image_gen.py` | 识图、生图 API 实现 |

### 会话与记忆

| 模块 | 说明 |
|------|------|
| `sessions.py` | 对话持久化 |
| `user_memory.py` | 跨会话用户记忆 |
| `plan.py` | Plan / Todo |
| `operations.py` | 工具操作时间线 |

### 工具层 `friday/tools/`

Agent 通过 `registry.py` 注册可调用工具。  
**命名约定**：`friday/vision.py` 是 API 实现，`friday/tools/vision.py` 是 `@register_tool` 包装。

### 微信 `friday/weixin/`

OpenClaw Gateway + 消息桥接 + 设置向导（`setup.py`）。

### 扩展与调度

| 模块 | 说明 |
|------|------|
| `plugins.py` / `bundled.py` | GitHub 插件 vs 内置迁移 |
| `skills.py` / `rules.py` | 技能与行为规则 |
| `schedules.py` / `scheduler.py` / `task_runner.py` | 定时任务 |

## `web/` 前端

无打包器；`index.html` 按顺序加载脚本。全局命名空间 `window.Friday`（见 `utils.js`）。

| 文件 | 职责 |
|------|------|
| `app.js` | 启动、bootstrap |
| `chat.js` | 对话区、流式 Markdown |
| `settings.js` / `providers.js` | 设置页、服务商 UI |
| `sessions.js` / `plan.js` / `history.js` | 会话、计划、操作历史 |
| `styles.css` | 设计 token + 全部样式（体量最大） |

详见 [web/README.md](../web/README.md)。

## `friday/api/` 路由（自 `server.py` 拆出）

| 模块 | 职责 |
|------|------|
| `routes/settings.py` | `/api/settings`、测试连接 |
| `routes/sessions.py` | 会话 CRUD |
| `routes/chat.py` | WebSocket `/ws/chat` |
| `routes/plugins.py` | 插件、技能、规则、状态栏 |
| `routes/diagnostics.py` | health、更新检查 |
| `routes/static_pages.py` | 首页 HTML、`__FRIDAY_TOKEN__` 注入 |
| `weixin_routes.py` | `/api/weixin/*` |
| `chat_runtime.py` | Agent 实例缓存、Yolo 解锁、审批清除 |
| `settings_helpers.py` / `session_helpers.py` | 设置合并、会话序列化 |

uvicorn 入口仍为 `friday.server:app`；测试与 scheduler 可从 `friday.server` 导入兼容符号。

## `tests/` 布局

```
tests/
├── conftest.py      # tmp_appdata、workspace fixtures
├── agent/           # brain、context、plan、记忆
├── api/             # 认证、会话、设置 API
├── providers/       # 模型/视觉/生图服务商
├── tools/           # 本地工具、安全、插件
├── weixin/          # 微信桥与 Gateway
├── platform/        # 可移植性、版本、日志
└── e2e/             # Playwright UI（默认 pytest 忽略）
```

约 **108** 个 `test_*.py`；默认 `pytest` 启用 `--cov=friday`、`--cov-fail-under=55`。

## `scripts/` 分类

详见 [scripts/README.md](../scripts/README.md)。常用：

- 开发：`run-dev.cmd`
- 打包：`build.ps1`
- 发布：`publish-release.ps1`（双端 push + Release）
- 清理：`clean.ps1`

## 已知体量热点（后续可拆）

| 文件 | 行数级（2026-06） | 建议 |
|------|-------------------|------|
| `web/styles.css` | ~5250 | 按页面拆 CSS 或在构建阶段合并 |
| `web/settings.js` | ~1930 | 按 Tab 拆文件（见 IMPLEMENTATION-PLAN 3.3） |
| `image_gen.py` | ~1360 | 探测与生成可分子模块 |
| `api/routes/plugins.py` | ~510 | 插件/技能/规则可再拆 |
| `plugins.py` | ~720 | 安装迁移与 manifest 规范化 |

`server.py` 路由已迁入 `friday/api/routes/`；保持 `friday.server:app` 为 uvicorn 入口，避免改打包配置。

## 数据落盘

用户数据均在 `%APPDATA%\Friday\`，不在项目目录：

- `settings.json`、`.fernet_key`
- `sessions/`、`plugins/`、`skills.json`
- OpenClaw 状态在 `%USERPROFILE%\.openclaw\`

## 相关文档

- [FRIDAY-DEV-MANUAL.md](FRIDAY-DEV-MANUAL.md) — 开发细节
- [RELEASE.md](RELEASE.md) — 发布流程
- [image-gen.md](image-gen.md) — 生图配置
