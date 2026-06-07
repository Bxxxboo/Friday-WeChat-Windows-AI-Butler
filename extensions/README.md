# Friday 扩展插件

扩展插件通过 GitHub 仓库分发，仓库根目录放置 `friday-plugin.json`，星期五会从 raw.githubusercontent.com 下载并自动应用其中的**技能**与**规则**。

## 安装方式

1. **设置页**：打开「设置 → 扩展 → 插件」，输入 `owner/repo` 或 `owner/repo@分支` 后点击「从 GitHub 安装」。
2. **对话中**：让星期五使用 `install_friday_plugin` 工具（需用户审批）。

## Manifest 格式

文件名必须为 `friday-plugin.json`，放在仓库根目录：

```json
{
  "id": "my-plugin",
  "name": "我的扩展包",
  "version": "1.0.0",
  "description": "简短说明",
  "author": "你的名字",
  "skills": [
    {
      "id": "quick-backup",
      "label": "备份桌面",
      "icon": "💾",
      "category": "plugin",
      "prompt": "列出桌面文件并建议备份方案，先只读分析。"
    }
  ],
  "rules": [
    {
      "id": "tone",
      "title": "语气偏好",
      "content": "回答技术问题时优先给出步骤列表。",
      "enabled": true,
      "always_apply": true
    }
  ]
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 插件唯一 ID，仅字母数字与连字符 |
| `name` | 是 | 显示名称 |
| `version` | 否 | 版本号，默认 `1.0.0` |
| `skills` | 否 | 技能数组，安装后出现在欢迎页与 `/` 补全 |
| `rules` | 否 | 规则数组，注入 AI 系统提示 |

技能与规则在存储时会加上前缀 `{plugin_id}:`，避免与内置项冲突。

## 示例

本仓库 `extensions/demo-office/` 为官方示例，可在开发环境通过 API `install_plugin_from_manifest` 测试。

## 发布到 GitHub

1. 新建公开仓库，根目录提交 `friday-plugin.json`。
2. 用户安装时填写 `你的用户名/仓库名` 或 `你的用户名/仓库名@main`。
3. 更新 manifest 后，用户在设置页点击「更新」即可拉取最新版本。

## 卸载

设置页插件卡片点击「卸载」，或对话中使用 `uninstall_friday_plugin`（需审批）。

卸载会删除该插件的全部技能与规则，以及 `%APPDATA%/Friday/plugins/{id}/` 目录。
