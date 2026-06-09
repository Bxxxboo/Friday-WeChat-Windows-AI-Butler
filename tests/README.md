# `tests/`

pytest 套件，按业务域分子目录。共享 fixture 在根目录 `conftest.py`。

## 目录

| 目录 | 覆盖 |
|------|------|
| `agent/` | brain、context、plan、用户记忆、交互模式 |
| `api/` | 认证、会话 CRUD、设置、更新公告、自启 |
| `providers/` | 大模型/视觉/生图服务商与自定义端点 |
| `tools/` | 文件/Shell/Web 工具、安全、插件、MCP |
| `weixin/` | 微信桥、Gateway、OpenClaw 自启 |
| `platform/` | 可移植性、edition、日志、Win10 运行时 |

## 运行

```powershell
pip install -r requirements-dev.txt
pytest
pytest tests/providers/test_image_gen.py -q
```
