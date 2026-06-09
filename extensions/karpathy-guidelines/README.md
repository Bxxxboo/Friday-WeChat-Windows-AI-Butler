# Karpathy Guidelines（Friday 扩展）

来源：[forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills)（MIT）

- `SKILL.md` — 上游 Agent Skill 原文
- `friday-plugin.json` — 星期五插件 manifest（规则默认始终注入 + 欢迎页技能 chip）

安装：设置 → 扩展 → 插件 → 输入 `local:karpathy-guidelines` 或让 Agent 执行 `install_friday_plugin`（`local:karpathy-guidelines`）。

开发仓库内已随 `extensions/karpathy-guidelines/` 内置，可通过 API / 脚本 `install_local_plugin("karpathy-guidelines")` 写入 `%APPDATA%/Friday/`。
