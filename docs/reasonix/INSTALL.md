# Reasonix 开发环境安装指南（星期五项目）

本目录是 Cursor / Reasonix 共用的一套 **Rules + Skills + 用户偏好** 合集，用于在 Reasonix 中开发星期五时保持与 Cursor 一致的 AI 行为。

---

## 一、合集内容

### Rules（项目规则，始终或按 glob 生效）

| 文件 | 作用 | 对应 Cursor |
|------|------|-------------|
| `rules/karpathy-guidelines.md` | 编码行为准则：先思考、最小改动、可验证目标 | `.cursor/rules/karpathy-guidelines.mdc` |
| `rules/friday-ui-design.md` | 改 `web/` 时的 UI 规范与 Skill 索引 | `.cursor/rules/friday-ui-design.mdc` |
| `rules/version-and-github.md` | 版本 bump + Gitee/GitHub 双端发布 | `.cursor/rules/version-and-github.mdc` |

### Skills（按需加载）

| Skill | 路径 | 何时用 |
|-------|------|--------|
| **friday-dev** | `skills/friday-dev.md` | 改 Python 后端、工具、API、可移植性 |
| **friday-ui** | `skills/friday-ui.md` | 改 `web/` 前端（Vanilla JS） |
| **vision-bridge** | `../.reasonix/skills/vision-bridge.md` | Reasonix 看图：调用豆包/Ark |
| **karpathy-guidelines** | `.cursor/skills/karpathy-guidelines/SKILL.md` | 通用编码纪律 |
| **impeccable** | `.cursor/skills/impeccable/` | UI 审计、polish、critique |
| **design-taste-frontend** | `.cursor/skills/design-taste-frontend/` | 避免 AI slop 审美 |
| **ui-design-brain** | `.cursor/skills/ui-design-brain/` | 组件模式与 a11y |
| **micro-interactions** | `.cursor/skills/micro-interactions/` | 按钮/表单微交互 |
| **motion-dev-animations** | `.cursor/skills/motion-dev-animations/` | 滚动/入场动效（CSS 为主） |
| **better-icons** | `.cursor/skills/better-icons/` | Iconify 图标，勿用 emoji |
| **frontend-design** | `.cursor/skills/frontend-design/` | Anthropic 前端审美基线 |

### 用户偏好

| 文件 | 作用 |
|------|------|
| `user-rules.md` | 回答语言、git 纪律、代码风格等个人规则 |

---

## 二、一键安装（推荐）

在项目根目录（`E:\Friday` 或当前工作区）执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-reasonix-bundle.ps1
```

脚本会：

1. 将 `docs/reasonix/rules/` 复制到 `.reasonix/rules/`
2. 将 `docs/reasonix/skills/` 合并到 `.reasonix/skills/`
3. 保留已有 `.reasonix/scripts/`（如 `vision_bridge.py`）
4. 若存在 `E:\reasonix\workspace`，同步一份到该 Reasonix 工作区

---

## 三、Reasonix 手动安装

### 1. 项目级 Skills

将以下文件放入 **项目根** 的 `.reasonix/skills/`：

```
.reasonix/skills/
  vision-bridge.md      # 已有
  friday-dev.md         # 从 docs/reasonix/skills/ 复制
  friday-ui.md          # 从 docs/reasonix/skills/ 复制
```

### 2. 项目级 Rules

在 Reasonix 设置中将 `docs/reasonix/rules/*.md` 添加为 **Project Rules**，或复制到 `.reasonix/rules/`（若 Reasonix 支持目录加载）。

### 3. 用户级 Rules

打开 Reasonix → Settings → Rules，粘贴 `docs/reasonix/user-rules.md` 全文，或分段添加。

### 4. UI 重型 Skills（Impeccable 等）

完整 Skill 包在 `.cursor/skills/`，体积较大。**不要**只拷贝 SKILL.md，应整目录复制：

```powershell
# 在星期五项目根执行
$dst = "$env:USERPROFILE\.reasonix\skills"   # 按 Reasonix 实际路径调整
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item -Recurse -Force .cursor\skills\impeccable $dst\impeccable
Copy-Item -Recurse -Force .cursor\skills\ui-design-brain $dst\ui-design-brain
# … 其他按需复制
```

若 Reasonix 与 Cursor 共用同一工作区（`E:\Friday`），则 **无需重复安装** `.cursor/skills/`，Reasonix 可直接读取。

---

## 四、Vision Bridge 依赖

```powershell
pip install cryptography openai pillow
python .reasonix/scripts/vision_bridge.py "C:\path\to\image.png"
```

配置与星期五共用：`%APPDATA%\Friday\settings.json` + `.fernet_key`。

---

## 五、验证安装

1. 在 Reasonix 中打开 `E:\Friday`
2. 提问：「改 settings.js 时要注意什么？」→ 应引用 DESIGN.md、Vanilla JS、双主题
3. 粘贴截图提问 → 应先调用 `vision_bridge.py`，而非假装能看见
4. 要求发布 patch → 应提到 bump `friday/version.py` + 双远端 push

---

## 六、维护

| 变更类型 | 更新位置 |
|----------|----------|
| 新增项目 Rule | `docs/reasonix/rules/` + `.cursor/rules/` |
| 新增 Friday Skill | `docs/reasonix/skills/` + `.reasonix/skills/` |
| UI 设计 Skill 升级 | `.cursor/skills/<name>/` |
| 用户偏好 | `docs/reasonix/user-rules.md` |

改完后重新运行 `scripts\install-reasonix-bundle.ps1` 同步到 `.reasonix/`。
