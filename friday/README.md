# `friday` 包

Windows 桌面 AI 管家的 Python 后端。从 [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) 查看完整架构图。

## 快速定位

| 要改什么 | 先看 |
|----------|------|
| 对话 / 工具循环 | `agent.py`, `brain.py`, `tools/` |
| HTTP / WebSocket | `server.py`（装配）, `api/routes/`, `api/chat_runtime.py`, `api/schemas.py` |
| 设置页对应 API | `api/routes/settings.py`, `api/settings_helpers.py`, `storage.py` |
| 生图 / 识图 | `image_gen.py`, `vision.py`（实现）；`tools/image_gen.py`, `tools/vision.py`（工具） |
| 微信远程 | `weixin/` |
| 桌面窗口 | `desktop.py`, `win32_chrome.py` |
| 安全与审批 | `safety.py` |
| 用户数据路径 | `paths.py`, `edition.py` |

## 子包

```
friday/
├── api/
│   ├── routes/        # settings、sessions、chat、plugins、diagnostics、static
│   ├── chat_runtime.py
│   ├── weixin_routes.py
│   └── schemas.py     # HTTP 请求/响应 Pydantic 模型
├── tools/             # Agent 可调用工具注册与实现
└── weixin/            # OpenClaw 微信桥
```

## 导入约定

- 业务代码使用 `from friday.xxx import ...`，避免 `from friday.server import` 除测试外的场景。
- 新增 HTTP 模型放 `api/schemas.py`；新增路由放 `api/routes/` 对应模块，并在 `server.py` 调用 `register_*_routes`。
