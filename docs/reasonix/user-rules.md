# 用户级 Rules（Reasonix / Cursor 通用）

## 沟通

- **回答使用简体中文**
- 改代码前先读现有代码风格
- 代码引用用 `startLine:endLine:filepath` 格式
- 不要过度 bold / 反引号装饰

## Git

- **不要擅自 `git commit`**，除非用户明确要求
- 不要 `git push --force` 到 main/master
- 不要改 git config

## 编码原则

1. **最小范围**：只改与任务直接相关的代码
2. **避免过度工程**：不为单次用途抽象；不加未请求的功能
3. **沿用惯例**：命名、类型、import 与周边文件一致
4. **注释**：只解释非显而易见的业务/技术细节
5. **测试**：仅在有意义的场景添加；不测试显然行为

## 星期五专项

- 前端：**Vanilla JS**，不引入 React/Vue（除非用户明确要求）
- UI 色值用 `web/styles.css` CSS 变量，见 `DESIGN.md`
- 用户数据在 `%APPDATA%\Friday\`，不在仓库内
- 发布时同步 bump `friday/version.py` 并 push Gitee + GitHub

## 执行

- 这是真实环境，必须自己跑命令验证，不要只给建议
- 多步任务先列可验证的成功标准，再实施
