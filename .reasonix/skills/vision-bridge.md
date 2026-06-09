---
name: vision-bridge
description: 通过豆包/Ark 视觉模型识别图片 — 用户发图时必须先调用 describe_image，禁止假装能直接看见图片
---
# Vision Bridge — 图片识别技能

你（Reasonix Code）本身无法直接看图。本技能让你通过火山引擎豆包/Ark 多模态 API 把图片转成文字描述，再据此回答用户。

## 铁律（必须遵守）

1. **用户提到图片、截图、界面、照片、图表、贴图时，必须先调用 `vision_bridge.py` 识别，禁止假装能直接看见图片内容。**
2. 用户粘贴的截图通常在 `C:\Users\Bxxxboo\AppData\Local\Temp\reasonix-pasted-images\` 下。
3. 视觉 API 失败时如实告知用户检查 Key、端点 ID、网络，**不要瞎猜图片内容**。
4. 识别完成后根据返回的文字描述回答用户，**勿编造未识别的内容**。

## 使用方式

```
python .reasonix/scripts/vision_bridge.py "<图片绝对路径>" "<可选自定义提示>"
```

### 示例

```bash
# 基础识别
python .reasonix/scripts/vision_bridge.py "C:\Users\Bxxxboo\Desktop\screenshot.png"

# 带自定义提问
python .reasonix/scripts/vision_bridge.py "C:\Users\Bxxxboo\Desktop\error.png" "读出图中的错误代码和具体报错信息"
```

### 参数说明

- 第一个参数（必填）：图片的绝对路径，支持 PNG / JPEG / GIF / WebP / BMP
- 第二个参数（可选）：自定义提示词，不填则使用默认的全面描述

## 工作流程

1. 用户发图或问图片内容 → 确定图片路径
2. 调用 `python .reasonix/scripts/vision_bridge.py "<路径>"`
3. 读取返回的文字描述
4. 基于描述回答用户问题

## 配置

- API Key / 端点 / 模型：自动从 `%APPDATA%/Friday/settings.json` 读取（与星期五共用配置）
- API 地址：`https://ark.cn-beijing.volces.com/api/v3`
- 密钥解密：自动通过 `%APPDATA%/Friday/.fernet_key` 解密

## 常见问题

| 现象 | 处理 |
|------|------|
| `[vision-bridge] HTTP 404` | 端点 ID 错误或已过期；打开星期五 → 设置 → API 连接 → 视觉辅助重新配置 |
| `[vision-bridge] 视觉辅助未启用` | settings.json 中 vision_enabled 为 false |
| `[vision-bridge] 图片不存在` | 确认路径正确，截图可能在 Temp 目录中 |
| cryptography 模块缺失 | `pip install cryptography` |
