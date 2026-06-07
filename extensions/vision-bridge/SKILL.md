# Vision Bridge — 星期五内置版

基于 [vision-bridge-setup](file:///E:/reasonix/workspace/.reasonix/skills/vision-bridge-setup.md) 集成，无需单独 MCP 进程。

## 配置

1. 打开 **设置 → API 连接 → 视觉辅助模型（豆包/Ark）**
2. 勾选「启用视觉辅助」
3. 填写火山引擎 Ark API Key（`ark-` 开头）
4. **视觉模型/端点** 填推理接入点 ID（`ep-2026...`），不是裸模型名
5. Base URL 默认 `https://ark.cn-beijing.volces.com/api/v3`

## 工具

- `describe_image` — 发图给豆包，返回文字描述
- `vision_status` — 检查是否已配置
- `screenshot` — 可先截屏再 describe_image

## 安装插件包

设置 → 扩展 → 插件 → 安装 `local:vision-bridge`（或从推荐列表安装）。
