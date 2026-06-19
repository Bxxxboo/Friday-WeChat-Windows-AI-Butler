# Friday-WeChat-Windows-AI-Butler

**微信能遥控的 Windows AI 电脑管家——大模型听懂人话，本地工具真正动手。**

中文产品名：**星期五**。它不只会聊天，还能在你授权的范围内直接操作本机：整理文件、生成文档、运行脚本、查看系统、生图识图，并把执行结果清清楚楚反馈给你。

和普通网页对话最大的区别是：**意图由大模型理解，动作在本地完成**。你说「帮我把下载文件夹里上周的截图挪到归档目录」，它会先扫描、给出计划，再在需要你点头时通过专用工具执行——而不是只输出一段「你可以手动这样做」的文字。

### 为什么叫 WeChat · Windows · AI Butler

- **Windows**：原生桌面应用（WebView2 小窗），数据落在 `%APPDATA%/Friday/`，无需把文件上传到云端再处理。
- **AI Butler**：多模型支持（DeepSeek、火山方舟等可配置），Agent / Ask / Yolo 等交互模式，28+ 本地工具覆盖文件、系统、文档、剪贴板、定时任务等。
- **WeChat**：通过 OpenClaw 桥接，**手机微信即可远程指挥这台电脑**——发指令、收回复、在聊天里点「同意/拒绝」完成危险操作审批。

帮你整理文件、查看系统、生成文档、执行日常电脑事务——说人话就行，不用懂技术。

**当前版本：1.4.10**（以 [`friday/version.py`](friday/version.py) 为准；发版时与官网 `download.json` 同步）

## 功能

- 小窗口桌面应用，对话即入口
- **设置页填写 DeepSeek API Key**（保存在 `%APPDATA%/Friday/settings.json`）
- 左侧对话列表，**会话持久化到 `%APPDATA%/Friday/sessions/`**
- 助手回复支持 **Markdown** 流式输出
- **生图**：OpenAI 兼容 / 火山方舟，结果写入会话历史
- **视觉辅助**：豆包 / Ark 识图（截图粘贴或文件路径）
- **微信端 AI**：手机微信远程指挥本机（OpenClaw 桥接）
- 设置：**API / 文件夹 / 外观 / 日志 / 安全与更新 / 扩展 / 定时任务**
- **更新公告**：升级后自动展示版本说明，设置页可查看历史
- 操作历史时间线、技能与规则、插件扩展
- 28+ 本地工具：文件整理、系统体检、文档生成、截屏、剪贴板等

## 快速开始

```powershell
cd 星期五
powershell -ExecutionPolicy Bypass -File setup.ps1
.\.python-env\Scripts\pythonw.exe run.py
```

首次使用：启动后会引导你 **连接 AI 服务** 并 **选择默认文件夹**（约 3 步）。  
首次启动会自动创建默认操作文件夹：`文档/星期五`（或 `Documents/Friday`）。

## 打包为 .exe（分发给用户）

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
```

产物：`dist/Friday/Friday.exe`（onedir 文件夹分发，含 `_internal/`，主程序无需安装 Python；旧构建可能仍为 `dist/星期五/星期五.exe`）

**运行要求：**

- Windows 10/11
- 已安装 [WebView2 运行时](https://developer.microsoft.com/microsoft-edge/webview2/)（Win11 通常已内置）
- 若使用 Agent Python 脚本功能：另需系统 Python 3.11+（见下方「移植到新电脑」）

双击 exe 即可使用，数据仍保存在 `%APPDATA%/Friday/`。

创建桌面快捷方式：

```powershell
powershell -ExecutionPolicy Bypass -File release/create-shortcut.ps1
```

开发模式使用 `.python-env\Scripts\pythonw.exe` 启动 `run.py`；打包后可将快捷方式改为指向 `dist/Friday/Friday.exe`。

## 移植到新电脑

### 方式 A：拷贝 exe 文件夹（推荐给测试机）

1. 在本机打包：`powershell -ExecutionPolicy Bypass -File scripts/build.ps1`
2. 将整个 **`dist/Friday/`** 文件夹拷到新电脑（不要只拷单个 exe；旧包目录名可能为 `dist/星期五/`）
3. 确认新电脑已装 [WebView2 运行时](https://developer.microsoft.com/microsoft-edge/webview2/)（Win11 一般已有）
4. 双击 `Friday.exe` 测试；首次使用会走引导填 API Key、选文件夹

**注意**：exe 不含 Agent 用的系统 Python。若要用 `run_python` 跑数据分析脚本，新电脑还需：

```powershell
winget install Python.Python.3.12
```

然后在应用设置页「初始化 Python 环境」。

### 方式 B：源码开发安装

1. 安装 Python 3.11+（推荐 3.12）
2. 拷贝项目源码（**不要**拷贝 `.venv/`、`.python-env/`、`build/`、`dist/`）
3. 在新目录执行 `setup.ps1`，再运行 `scripts\run-dev.cmd` 或 `.\.python-env\Scripts\pythonw.exe run.py`

### 迁移用户数据（可选）

配置与对话在 **`%APPDATA%\Friday\`**，不在项目目录。若要带走旧数据，需整文件夹拷贝，尤其：

| 文件 | 说明 |
|------|------|
| `settings.json` | 设置 |
| `.fernet_key` | API Key 解密密钥（必须与 settings 成对） |
| `sessions/` | 对话历史 |
| `plugins/`、`skills.json` | 插件与自定义技能 |

拷贝后在新电脑打开设置，**检查「默认操作文件夹」**是否为有效路径（旧机器的 `C:\Users\旧用户\...` 需改成本机路径）。

**不要**直接拷贝工作区里的 `.python-env/`，到新电脑后重新初始化即可。

## 下载与自动更新

| 平台 | 地址 |
|------|------|
| **Gitee Releases（默认，国内免 VPN）** | https://gitee.com/Bxxxboo/friday/releases |
| **GitHub Releases（备用）** | https://github.com/Bxxxboo/Friday-WeChat-Windows-AI-Butler/releases |

应用内：**设置 → 安全与更新 → 检查更新**，优先从 Gitee 拉取 `Friday-Windows.zip`。

升级后会弹出 **更新公告**；也可在同一页面点击「查看更新历史」。完整文字见 [CHANGELOG.md](CHANGELOG.md) 与 `assets/changelog.json`。

## 发布与双端同步（维护者）

详见 [docs/RELEASE.md](docs/RELEASE.md)。

```powershell
$env:GITEE_TOKEN = '令牌'
powershell -ExecutionPolicy Bypass -File scripts/publish-release.ps1 `
  -GitHubRepoName Friday-WeChat-Windows-AI-Butler
```

同步 GitHub + Gitee 代码，并上传 Release 安装包与更新说明。

## 工程维护

```powershell
powershell -ExecutionPolicy Bypass -File scripts/clean.ps1
```

清理 `build/`、`dist/`（需先关闭正在运行的 exe）及源码中的 `__pycache__`。构建产物不入库，见 `.gitignore`。

生成给其他电脑用的安装压缩包：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/make-release.ps1
```

产物：`release/Friday-Windows.zip`（含 exe、`安装教程.txt`、快捷方式脚本）。

**两个 Python 环境（有意分离，勿合并）：**

| 目录 | 用途 |
|------|------|
| 项目 `.python-env/` | 星期五应用本身（FastAPI、pywebview 等，`setup.ps1` 创建） |
| 工作区 `.python-env/` | Agent 执行脚本时的隔离环境（pandas 等，由设置页在工作区初始化） |

## 技术栈

- 前端：`HTML + CSS + JavaScript`（模块化：`utils.js` / `sessions.js` / `settings.js` / `chat.js` / `releaseNotes.js` 等）
- 后端：`FastAPI + WebSocket`
- 桌面壳：`pywebview`（Edge WebView2）
- 配置存储：`%APPDATA%\Friday\settings.json`

## 开发模式（浏览器调试）

```powershell
.\.python-env\Scripts\uvicorn friday.server:app --reload --port 8765
```

浏览器访问 `http://127.0.0.1:8765`

## 测试

```powershell
pip install -r requirements-dev.txt
pytest                    # 单元/集成 + 覆盖率 ≥55%（默认忽略 tests/e2e）
pytest --no-cov           # 快速跑，不统计覆盖率
pytest tests/e2e/         # Playwright UI e2e
```

覆盖率配置见 `pytest.ini` / `pyproject.toml`；详见 [tests/README.md](tests/README.md)。

## 文档

| 文件 | 说明 |
|------|------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | **源码架构与模块地图** |
| [CHANGELOG.md](CHANGELOG.md) | 版本更新日志 |
| [docs/RELEASE.md](docs/RELEASE.md) | 发布与双端同步流程 |
| [docs/image-gen.md](docs/image-gen.md) | 生图功能配置 |
| [docs/archive/PLAN.md](docs/archive/PLAN.md) | 历史项目计划（归档） |

各目录另有 README：`friday/`、`web/`、`scripts/`、`tests/`。

## 项目结构

```
星期五/
├── run.py                  # 入口 → friday.desktop.main()
├── pyproject.toml          # pytest 配置
├── assets/changelog.json
├── friday.spec
├── friday/
│   ├── README.md           # 包内模块索引
│   ├── desktop.py          # pywebview 桌面壳
│   ├── server.py           # FastAPI 装配、token 中间件
│   ├── api/routes/         # HTTP / WebSocket 路由（settings、sessions、chat、plugins…）
│   ├── api/schemas.py      # HTTP 请求/响应模型
│   ├── agent.py / brain.py # Agent 与 LLM
│   ├── tools/              # 本地可调用工具
│   └── weixin/             # 微信 OpenClaw 桥
├── web/                    # 前端 SPA（见 web/README.md）
├── tests/                  # pytest，按 agent/api/providers/… 分子目录
├── scripts/                # 构建、发布、安装（见 scripts/README.md）
├── release/                # 用户 zip 附件
├── docs/ARCHITECTURE.md
└── extensions/             # 内置插件
```
