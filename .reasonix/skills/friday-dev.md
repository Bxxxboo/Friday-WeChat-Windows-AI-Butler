---
name: friday-dev
description: 开发星期五 Python 后端、FastAPI、Agent、工具注册、可移植性与发布。改 friday/、tests/、scripts/ 时启用。
---
# Friday 后端开发 Skill

## 技术栈

| 层 | 技术 |
|----|------|
| 语言 | Python 3.11+（推荐 3.12） |
| Web | FastAPI + Uvicorn |
| 桌面壳 | pywebview (WebView2 / edgechromium) |
| LLM | OpenAI 兼容 API（DeepSeek / MiMo / 自定义） |
| 打包 | PyInstaller (`scripts/build.ps1`) |

## 目录地图

```
friday/
  desktop.py      # 入口：WebView2 + 后台线程启 server
  server.py       # FastAPI 路由、WebSocket、静态 web/
  agent.py        # 工具循环、审批、取消
  brain.py        # system prompt、OpenAI 调用、前缀缓存
  storage.py      # settings.json（Fernet 加密 Key）
  sessions.py     # 会话持久化
  tools/          # 本地工具（registry 装饰器注册）
  portability.py  # 可移植性自检 / 修复
  portable_bundle.py  # 配置包 import/export
  weixin/         # 微信 OpenClaw 桥接
web/              # Vanilla JS 前端
tests/            # pytest
scripts/          # 构建、发布、快捷方式
docs/             # 计划与手册
```

## 用户数据（勿入库）

| 路径 | 内容 |
|------|------|
| `%APPDATA%\Friday\settings.json` | API Key、模型、文件夹 |
| `%APPDATA%\Friday\sessions\` | 对话历史 |
| `%APPDATA%\Friday\friday.log` | 运行日志 |
| 工作区（如 `Documents/星期五`） | 用户文件、`.python-env` |

## 添加新工具

1. 在 `friday/tools/<module>.py` 用 `@tool` 装饰器定义函数
2. 若新模块：加入 `registry.py` 的 `_EAGER_MODULES` 或 `_LAZY_MODULES`
3. 在 `safety.py` 评估风险等级（如需审批）
4. 补 `tests/test_tools_*.py`

## 启动与测试

```powershell
cd E:\Friday
.\.python-env\Scripts\pip install -r requirements.txt
.\.python-env\Scripts\pythonw.exe run.py          # 桌面
.\.python-env\Scripts\python.exe -m pytest tests/ -q
```

## 常见坑

- **缺模块**：`registry.py` eager import 多个 tools 子模块，缺文件会导致启动失败
- **视觉 API**：Base URL 填 API 根（如 `https://ark.cn-beijing.volces.com/api/v3`），不要混 MiMo 完整 chat URL
- **单实例**：端口 58765；重复启动会激活已有窗口并退出
- **可移植性**：见 `friday/portability.py` 与 `docs/archive/PORTABILITY-PLAN.md`

## 发布

见 `docs/reasonix/rules/version-and-github.md` 或 `.cursor/rules/version-and-github.mdc`
