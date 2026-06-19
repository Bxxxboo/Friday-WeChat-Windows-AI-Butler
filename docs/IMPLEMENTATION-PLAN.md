# Friday 改进实施方案

> 来源：2026-06-18 全面评估（总分 7.0/10）  
> 原则：**路线 A — 先让用户装得上、更新不翻车，再慢慢修结构和性能**  
> 任务明细 backlog 见 `TODOS.md`；本文件只回答：**先干什么、后干什么、怎样算做完**。  
> **版本号不在此计划里定**；发版时按 `publish-release.mdc` 再 bump 和写 changelog。

---

## 1. 一句话结论

**代码已经写了不少，但还没交给用户。** 当前最该做的是 **把已有改动走完发版闭环**（打包、双端 Release、官网、人工抽测）。  
闭环之后，再按顺序做：**插件格式统一 → 测试覆盖率 → 文档对齐 → 启动加速 → 设置页拆分 → 有限多 Agent**。

---

## 2. 现在卡在哪

| 情况 | 说明 |
|------|------|
| 测试 | **773** 项，本地已通过 |
| 代码 | P0/P1/P2 主体 + 更新后设置持久化 + SciPilot 欢迎页名称，**在工作区，未 commit、未 Release** |
| 用户仍可能遇到 | 没装到新包；旧包更新后设置回退；SciPilot 显示「未命名」（需新包或刷新插件） |

**什么叫「做完」：** 不是 merge 代码，而是 **Gitee + GitHub 都发了安装包、官网与包内版本一致、你亲手测过 PPT 技能内置与更新后设置不丢**。

---

## 3. 四步路线图（按顺序，不要跳）

```text
第 1 步  交付闭环        把已有改动真正发给用户（1～2 天）  ← 现在在这里
第 2 步  质量与文档      插件格式、覆盖率、文档、状态栏（约 1～2 周）
第 3 步  性能与维护      启动、前端拆分、类型与依赖（约 2～4 周，可拆多次发布）
第 4 步  有限多 Agent    ✅ 已实现（默认开，max=3）
```

下面每一步：**用户能得到什么 → 你要做什么 → 怎样算验收通过**。

---

## 第 1 步：交付闭环（当前必做）

### 用户能得到什么

- 安装包内嵌 **ppt-master** 技能资源，**不必再从 GitHub 拉 skill**；做 PPT 仍须 **大模型 API 联网**  
- 启动时能看到 **PPT 资源是否就绪**  
- **更新后** 大模型服务商、视觉辅助开关 **尽量保持原样**  
- 欢迎页 **「科研数据可视化」** 不再叫「未命名」

### 你要做什么（按顺序）

**A. 发版准备（具体版本号发版时再定）**

1. 按 `publish-release.mdc` 写 `assets/changelog.json` + `CHANGELOG.md`（写清：PPT 离线、包体积、设置持久化、SciPilot 名称等）  
2. bump `friday/version.py`、`scripts/version_info.py`  
3. commit 当前所有相关改动  

**B. 打包与发布**

4. `pytest tests/ -q --ignore=tests/e2e`，再跑 `pytest tests/e2e/`  
5. `scripts\make-release.ps1`  
6. `scripts\publish-release.cmd -GitHubRepoName Friday-WeChat-Windows-AI-Butler`（Gitee + GitHub + 官网）

**C. 发布后人工抽测（缺一不可）**

- [ ] **联网** 冷启动，试「做 PPT / 读 ppt-master」（确认不再从 GitHub 拉 skill）  
- [ ] `/api/health` 里 ppt-master 为 ready  
- [ ] **覆盖安装** 后，大模型仍是原来那家（不是默认 DeepSeek）  
- [ ] **覆盖安装** 后，视觉辅助仍是你关/开的状态  
- [ ] 欢迎页 chip 是「科研数据可视化」，不是「未命名」  

changelog 里提醒：换机或手动拷配置时须带上 `%AppData%\Friday\credentials\`（含 `.fernet_key`）。

### 本步代码已就绪、不必再开发

- P0：ppt 完整打包、extensions 校验、bundled skill 健康检查  
- P1：证据链、痛点记忆、agent 拆分等（写进本次发版公告即可）  
- 评估修复：`align_llm_active_from_profile`、保存时同步 `vision_enabled` 到 profile  
- SciPilot：`friday-plugin.json` 已改成 Friday 标准字段  

**预计时间：** 半天～1 天（含打包等待）

---

## 第 2 步：质量与文档

> **前提：** 第 1 步已发布且抽测通过。

### 用户能得到什么

- 装 GitHub 插件时 **不再出现「未命名」**（即使作者没用 `label`）  
- 有 **测试覆盖率底线**，改代码不易 silent 回归  
- README、架构文档 **与代码现状一致**

### 任务清单（4 项，可并行）

#### 2.1 插件格式自动纠正

- **问题：** 有的插件用 `title`，Friday 只认 `label`。  
- **做法：** `friday/plugins.py` 安装/刷新时：`label ← label 或 title`，`id ← id 或 name`，缺 `prompt` 则从 description + SKILL.md 补。  
- **验收：** 旧 SciPilot 格式安装后 chip 有正常中文名。  
- **时间：** 约半天。  
- **状态（2026-06-19）：** ✅ 已实现 + 启动迁移；欢迎页不再展示「插件技能」chip（规则仍生效）。

#### 2.2 测试覆盖率门槛

- **问题：** 773 个测试，但不知道覆盖了多少代码。  
- **做法：** 加 `pytest-cov`，`--cov-fail-under=55`（以后可提到 65）。  
- **验收：** 低于门槛时 pytest 失败。  
- **时间：** 约半天。  
- **状态（2026-06-19）：** ✅ `requirements-dev.txt` + `pyproject.toml` 默认启用；GUI 入口 omit；`pytest --no-cov` 可跳过。

#### 2.3 文档与现状对齐

- **问题：** README、ARCHITECTURE 有过时描述。  
- **做法：** 发版脚本或小手稿同步 README 中的版本展示；更新 ARCHITECTURE 模块表与行数。  
- **验收：** 文档与当前代码结构一致。  
- **时间：** 约 2 小时。  
- **状态（2026-06-19）：** ✅ README 版本/打包路径/测试说明；ARCHITECTURE `api/routes/` 与行数热点；`friday/README.md` 路由索引。

#### 2.4 设置保存与状态栏一致

- **问题：** 保存设置后，状态栏偶尔仍显示旧状态。  
- **做法：** 补测试 + 开发手册「发版前检查清单」。  
- **验收：** 改 `vision_enabled` 并保存后，状态栏跟着变。  
- **时间：** 约 1 天。  
- **状态（2026-06-19）：** ✅ `syncStatusBarAfterSettingsSave` + `refreshStatusBar({ force })` 穿透启动阶段；视觉/生图保存路径统一；`tests/api/test_settings_status_bar.py`；`FRIDAY-DEV-MANUAL.md` §13.1 检查清单。

完成后再走一轮发版流程（同第 1 步 B/C）。

**预计时间：** 2～3 个工作日（不含打包）

---

## 第 3 步：性能与维护

> **前提：** 第 1 步在用户侧稳定。可拆成多次小发布，不必一次做完。

| 顺序 | 解决什么 | 做什么 | 验收 | 时间 |
|------|----------|--------|------|------|
| 3.1 | 启动偏慢 | `brain.py` 用时再加载工具，不要启动全量 import | 测试全绿；import 链变短 | 1～2 天 |
| 3.2 | 不知道慢在哪 | 启动分段计时（splash → API → health → PPT 就绪） | log 可读每段 ms | 半天 |
| 3.3 | `settings.js` 近 2000 行 | 按大模型/视觉/安全/公共拆 js，UI 行为不变 | 设置页 E2E 仍过 | 2～3 天 |
| 3.4 | 类型检查面窄 | mypy 扩到 storage、safety、credentials 等 | `run-typecheck.cmd` 零报错 | 1～2 天 |
| 3.5 | 依赖漂移 | release 用 lock 文件；可选 pip-audit | 两次构建依赖一致 | 半天 |

**状态（2026-06-19）：**

| 项 | 状态 |
|----|------|
| 3.1 | ✅ `registry` import 时不加载工具；`brain.py` 用时 import；`tests/tools/test_registry_startup.py` |
| 3.2 | ✅ `friday/boot_timing.py` + `desktop.py` / `server.py` 分段 log |
| 3.3 | ✅ 拆为 `settings-theme.js`、`settings-providers.js`、`settings.js`（`index.html` 已 bump） |
| 3.4 | ✅ `run-typecheck.cmd` 扩至 storage/safety/credentials/settings_helpers；`follow_imports=skip` |
| 3.5 | ✅ `requirements-lock.txt` + `sync/verify-requirements-lock.ps1` |

---

## 第 4 步：有限多 Agent

> **前提：** 第 3 步 **3.1 启动加载** 完成。功能 **默认开启**（`max_sub_agents=3`）。

`TODOS.md` P1-6 剩余：

- [x] 固定 eval：复杂任务产出可用 plan  
- [x] 超过上限时排队，不无限 spawn  
- [x] 子 Agent 不能调删除文件、PowerShell、微信高危工具  

**状态（2026-06-19）：** ✅ `friday/sub_agents.py`：`SubAgentPool`、`orchestrate_bounded_sub_agents`（Planner + Research）、`sub_agent_tool_allowed`；`agent.py` 写入 plan anchor；`tests/agent/test_sub_agents.py`（含固定 eval case）。

**预计时间：** 3～5 个工作日 + eval 调优  

**明确不做：** 无限群狼、ToolRegistry 大重写、全库 TypedDict（见 `TODOS.md` P3）。

**关闭：** `settings.json` 中 `"multi_agent_enabled": false`；并发上限 `"max_sub_agents"` 默认 3（1～3）。

---

## 4. 每次发布同一套检查

**发版前**

```powershell
pytest tests/ -q --ignore=tests/e2e
pytest tests/e2e/
scripts\make-release.ps1
```

若改了 `storage.py` / `credentials_store.py`：

```powershell
python -m pytest tests/api/test_credentials_store.py tests/providers/test_llm_profiles.py tests/providers/test_category_profiles.py -q
```

**发版后**

```powershell
git ls-remote origin refs/heads/main
git ls-remote gitee refs/heads/main
# 两行 SHA 相同

(Invoke-WebRequest -Uri "https://fridayaiagent.vercel.app/download.json" -UseBasicParsing).Content
# version 与 friday/version.py 一致
```

**交付完成 =** 测试绿 + 双端 zip + 官网 version 对 + 本步人工抽测打勾。

---

## 5. 可穿插、不挡主线的事

| 事项 | 说明 | 优先级 |
|------|------|--------|
| 开 Yolo 前二次确认 | 设置页说明危险能力 | 中 |
| 装 GitHub 插件前提示未签名 | 一句警告 | 低 |
| 便携包文档强调 credentials | 换机必拷 | 中 |
| 拆分 `styles.css` | 5000+ 行，不紧急 | 低 |

---

## 6. 出问题怎么回滚

| 现象 | 怎么办 |
|------|--------|
| 更新后设置还是丢 | 发 **patch 热修**，只动 `storage.py` / `llm_profiles.py` |
| 延迟加载后 Agent 调不了工具 | revert 该 PR，全量 pytest |
| 覆盖率门槛卡 CI | 临时降门槛一周，再拉回 |
| 设置页拆分 UI 回归 | revert 对应 PR |

---

## 7. 进度

| 步骤 | 主题 | 状态 |
|------|------|------|
| 1 交付闭环 | 已有改动发布 + 抽测 | ✅ 1.4.9 已发；1.4.10 补丁（更新/安装体验） |
| 2 质量与文档 | 插件、覆盖率、文档、状态栏 | ✅ 2.1–2.4 已完成（待发版） |
| 3 性能与维护 | 启动、settings 拆分、类型与依赖 | ✅ 3.1–3.5 已完成（待发版） |
| 4 有限多 Agent | P1-6 | ✅ 已实现（默认开，max=3） |

---

## 8. 相关文档

- 任务 backlog：`TODOS.md`  
- 发版流程（含版本号与 changelog）：`.cursor/rules/publish-release.mdc`  
- 修 bug 纪律：`.cursor/skills/surgical-bugfix/SKILL.md`  
- 架构说明：`docs/ARCHITECTURE.md`
