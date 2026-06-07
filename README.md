# 星期五

Windows AI 电脑管家：大模型理解意图 + 本地工具真正动手。

帮你整理文件、查看系统、生成文档、执行日常电脑事务——说人话就行，不用懂技术。

## 功能

- 小窗口桌面应用，对话即入口
- **设置页填写 DeepSeek API Key**（保存在 `%APPDATA%/Friday/settings.json`）
- 左侧对话列表，**会话持久化到 `%APPDATA%/Friday/sessions/`**
- 助手回复支持 **Markdown** 流式输出
- 设置：**API 连接 / 默认操作文件夹 / 通用 / 安全与审批 / 定时任务**
- 操作历史时间线、定时任务
- 28 个本地工具：文件整理、系统体检、文档生成、截屏、剪贴板等

## 快速开始

```powershell
cd 星期五
powershell -ExecutionPolicy Bypass -File setup.ps1
.\.venv\Scripts\python run.py
```

首次使用：启动后会引导你 **连接 AI 服务** 并 **选择默认文件夹**（约 3 步）。  
首次启动会自动创建默认操作文件夹：`文档/星期五`（或 `Documents/Friday`）。

## 打包为 .exe（分发给用户）

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
```

产物：`dist/星期五/星期五.exe`（onedir 文件夹分发，含 `_internal/`，主程序无需安装 Python）

**运行要求：**
- Windows 10/11
- 已安装 [WebView2 运行时](https://developer.microsoft.com/microsoft-edge/webview2/)（Win11 通常已内置）
- 若使用 Agent Python 脚本功能：另需系统 Python 3.11+（见下方「移植到新电脑」）

双击 exe 即可使用，数据仍保存在 `%APPDATA%/Friday/`。

创建桌面快捷方式：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/create_shortcut.ps1
```

优先指向 `dist/星期五/星期五.exe`；若尚未打包，则回退为开发模式（`pythonw run.py`）。

## 移植到新电脑

### 方式 A：拷贝 exe 文件夹（推荐给测试机）

1. 在本机打包：`powershell -ExecutionPolicy Bypass -File scripts/build.ps1`
2. 将整个 **`dist/星期五/`** 文件夹拷到新电脑（不要只拷单个 exe）
3. 确认新电脑已装 [WebView2 运行时](https://developer.microsoft.com/microsoft-edge/webview2/)（Win11 一般已有）
4. 双击 `星期五.exe` 测试；首次使用会走引导填 API Key、选文件夹

**注意**：exe 不含 Agent 用的系统 Python。若要用 `run_python` 跑数据分析脚本，新电脑还需：

```powershell
winget install Python.Python.3.12
```

然后在应用设置页「初始化 Python 环境」。

### 方式 B：源码开发安装

1. 安装 Python 3.11+（推荐 3.12）
2. 拷贝项目源码（**不要**拷贝 `.venv/`、`.python-env/`、`build/`、`dist/`）
3. 在新目录执行 `setup.ps1`，用 `.\.venv\Scripts\python run.py` 启动

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

## GitHub 发布与自动更新

内置更新源：**https://github.com/Bxxxboo/friday**（修改 `friday/version.py` 里的 `GITHUB_REPO` 可更换）。

用户可在 **设置 → 通用 → 检查更新** 从 GitHub Releases 下载 `*-Windows.zip`。

### 首次发布

需安装 [Git](https://git-scm.com/) 与 [GitHub CLI](https://cli.github.com/)，并执行 `gh auth login`：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/publish-github.ps1
```

### 后续版本

1. 更新 `friday/version.py` 中的 `__version__`
2. `git tag v1.0.1 && git push origin v1.0.1`
3. Actions 工作流 `.github/workflows/release.yml` 自动构建并上传安装包

## 工程维护

```powershell
powershell -ExecutionPolicy Bypass -File scripts/clean.ps1
```

清理 `build/`、`dist/`（需先关闭正在运行的 exe）及源码中的 `__pycache__`。构建产物不入库，见 `.gitignore`。

生成给其他电脑用的安装压缩包：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/make-release.ps1
```

产物：`release/星期五-Windows.zip`（含 exe、`安装教程.txt`、快捷方式脚本）。

**两个 Python 环境（有意分离，勿合并）：**

| 目录 | 用途 |
|------|------|
| `.venv/` | 星期五应用本身（FastAPI、pywebview 等） |
| 工作区 `.python-env/` | Agent 执行脚本时的隔离环境（pandas 等，由设置页初始化） |

## 技术栈

- 前端：`HTML + CSS + JavaScript`（`utils.js` / `sessions.js` / `settings.js` / `chat.js` / `onboarding.js` / `history.js` / `schedules.js` / `app.js`）
- 后端：`FastAPI + WebSocket`
- 桌面壳：`pywebview`（Edge WebView2）
- 配置存储：`%APPDATA%\Friday\settings.json`

## 开发模式（浏览器调试）

```powershell
.\.venv\Scripts\uvicorn friday.server:app --reload --port 8765
```

浏览器访问 `http://127.0.0.1:8765`

## 测试

```powershell
pip install -r requirements-dev.txt
pytest
```

## 项目结构

```
星期五/
├── run.py
├── friday.spec          # PyInstaller 配置
├── tests/               # pytest
├── web/                 # 前端
│   ├── index.html
│   ├── styles.css
│   ├── onboarding.js
│   ├── history.js
│   ├── schedules.js
│   └── ...
├── scripts/
│   ├── build.ps1        # 一键打包
│   ├── clean.ps1        # 清理 build/dist/pycache
│   └── create_icon.py
├── docs/                # 项目计划等文档
├── friday/
│   ├── desktop.py       # 桌面窗口
│   ├── server.py        # API + WebSocket
│   └── tools/
└── assets/friday.ico
```
