# `web/` 前端

Vanilla JS 单页应用，由 `friday/server.py` 以静态文件 + 注入 `__FRIDAY_TOKEN__` 方式提供。

## 加载顺序（`index.html`）

1. `vendor/` — marked、DOMPurify
2. `utils.js` — `window.Friday` 命名空间、API 封装
3. `i18n.js`, `errorHints.js`, `mode.js`
4. 功能模块：`sessions.js`, `chat.js`, `settings.js`, `providers.js`, …
5. `app.js` — 最后执行 bootstrap

## 模块职责

| 文件 | 职责 |
|------|------|
| `app.js` | 启动、全局事件 |
| `chat.js` | 消息列表、流式渲染、审批 UI |
| `settings.js` | 设置页各 Tab 逻辑 |
| `providers.js` | 大模型 / 视觉 / 生图服务商选择 |
| `sessions.js` | 左侧会话列表 |
| `plan.js` | Plan / Todo |
| `history.js` | 操作历史时间线 |
| `skills.js` / `extensions.js` / `schedules.js` | 技能、插件、定时任务 |
| `onboarding.js` | 首次引导 |
| `weixin.js` | 微信桥设置 |
| `statusbar.js` | 底部状态栏 |
| `releaseNotes.js` | 更新公告 |
| `styles.css` | 全部样式与设计 token |

## 改 UI 前

- 产品/UI 规范见仓库根目录 `DESIGN.md`、`PRODUCT.md`。
- 静态资源改后需在 `index.html` bump `?v=` 缓存版本。

## 与后端对应

| 前端 | 后端 |
|------|------|
| `settings.js` | `/api/settings`, `/api/settings/test*` |
| `providers.js` | `/api/model-providers` |
| `chat.js` | `/ws/chat` |
| `weixin.js` | `/api/weixin/*` |
