---
name: friday-ui
description: 开发星期五 web/ 前端（Vanilla HTML/CSS/JS、WebView2 桌面壳）。改 UI、设置页、Onboarding 时启用。
---
# Friday 前端开发 Skill

## 必读文件

| 文件 | 作用 |
|------|------|
| `DESIGN.md` | 设计 token、组件规范 |
| `PRODUCT.md` | 产品定位（工具型，非营销页） |
| `web/styles.css` | CSS 变量与组件样式（单一事实来源） |
| `web/index.html` | 主壳结构 |
| `web/app.js` | 聊天、侧栏、路由 |
| `web/settings.js` | 设置页、可移植性自检/迁移向导 |
| `web/onboarding.js` | 首次引导 |

## 架构

- **无框架**：原生 JS 模块化（`<script type="module">`）
- **静态资源**：FastAPI 挂载 `web/`，版本 query `?v=` 缓存 bust
- **主题**：`html[data-theme="dark|light"]`，切换存 settings
- **桌面**：`html.desktop` 自定义标题栏；交互区 `no-drag`

## 改 UI 检查清单

- [ ] dark + light 主题都可读
- [ ] 新色值用 CSS 变量，不硬编码 hex
- [ ] 模态/输入/按钮可聚焦，WebView2 下可点击
- [ ] `prefers-reduced-motion` 尊重
- [ ] 中文 copy 简洁；错误有下一步指引（见 `friday/error_hints.py` + `web/errorHints.js`）

## API 调用

前端通过 `fetch('/api/...')` 访问后端；WebSocket 用于流式回复与微信推送刷新。

常用端点：`/api/chat/stream`、`/api/settings`、`/api/portable/audit`、`/api/health`

## 设计 Skills

大改 UI 前可读 `.cursor/skills/impeccable/SKILL.md`，或跑：

```bash
node .cursor/skills/impeccable/scripts/context.mjs
```

详见 `docs/reasonix/rules/friday-ui-design.md`
