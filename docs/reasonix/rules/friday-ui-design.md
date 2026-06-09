# 星期五前端 UI 设计规范

**适用：** `web/**`、`DESIGN.md`、`PRODUCT.md`

## 必读

1. **DESIGN.md** — 颜色、字体、组件 token
2. **PRODUCT.md** — 工具型桌面应用定位
3. **web/styles.css** — 实现单一事实来源

## 硬性约束

- **Vanilla JS**：无 React/Vue（除非用户明确要求）
- **双主题**：dark / light 均需可读
- **WebView2**：弹窗、输入、按钮 `-webkit-app-region: no-drag`
- **不硬编码色值**：用 `:root` / `html[data-theme="light"]` 变量
- **中文 UI** copy 简洁；错误提示 actionable

## 关联 Skills

| Skill | 用途 |
|-------|------|
| impeccable | UI 审计、polish、critique |
| design-taste-frontend | 避免 AI slop 模板 |
| ui-design-brain | 组件模式、a11y |
| micro-interactions | 微交互、easing |
| motion-dev-animations | 滚动/入场（本项目以 CSS 为主） |
| better-icons | Iconify，勿 emoji 顶替 |
| frontend-design | 基础前端审美 |

## Impeccable（可选）

```bash
node .cursor/skills/impeccable/scripts/context.mjs
```
