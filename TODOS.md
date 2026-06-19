# Friday 技术债与优化 Backlog

> **战略方向（2026-06-18 锁定）：路线 A — 交付优先**  
> 目标：装完就能用、更新不翻车。结构治理（agent 拆分等）穿插进行，平台化延后。

---

## P0 — 下一版必做（用户可感知）

### P0-1 安装包内嵌完整 ppt-master（离线可用）

**现状**

- `scripts/make-release.ps1` 发版前会 `sync_ppt_master_skill.ps1` 拉到 `extensions/ppt-master/`
- `friday.spec` 的 `_extension_datas()` **仍跳过** `ppt-master/` 下除 `friday-plugin.json` 外的所有文件
- 运行时靠 `ensure_bundled_skill_assets()` 从 GitHub 后台下载 → 断网/慢网用户点「做 PPT」才失败

**改动**

1. `friday.spec`：发版构建时打包完整 `extensions/ppt-master/`（与 make-release 同步后的内容一致）
2. `tests/test_packaging_spec.py`：断言 spec 不再排除 `ppt-master/scripts/svg_to_pptx.py`
3. 可选：发版后脚本校验 `dist/Friday/_internal/extensions/ppt-master/scripts/svg_to_pptx.py` 存在

**验收**

- [x] `friday.spec` 打包完整 `extensions/ppt-master/`（不再排除 skill 文件）
- [x] `tests/test_packaging_spec.py` 回归
- [x] `make-release` 调用 `verify-release-extensions.ps1`
- [ ] 断网冷启正式版实测（需发版包）
- [ ] 安装包体积增幅写入 changelog（发版时）

---

### P0-2 启动与 bundled skill 可观测

**现状**

- `/api/health` 仅有 backend / webview / gateway / python_env（`health_check.py`）
- `_bundled_skill_warmup` 失败只写 log，UI 无「PPT 资源准备中/失败」状态

**改动**

1. `server.py`：warmup 任务记录 `{plugin_id: pending|ready|failed|skipped}` 模块级状态
2. `health_check.py`：`services.bundled_skills` 返回各内置 skill 就绪状态
3. 前端状态栏或设置页：degraded 时展示「PPT 资源未就绪」+ 重试/诊断入口（最小：复用现有 status_bar 轮询 health）

**验收**

- [x] `GET /api/health` 返回 `services.bundled_skills.skills.ppt-master`
- [x] pending/failed 时 `degraded: true`
- [x] 启动 UI 提示（`app.js` connection status）
- [x] `tests/api/test_bundled_skills_health.py`

---

### P0-3 extensions 打包审计（发版门禁）

**现状**

- 仓库 `extensions/*/friday-plugin.json` 与 `_internal/extensions/` 可能不一致（历史 verify 目录已暴露）

**改动**

1. `scripts/verify-release-extensions.ps1`（或 pytest）：对比源 `extensions/` 与 `dist/Friday/_internal/extensions/` 的 manifest 列表 + ppt-master 关键文件
2. `make-release.ps1` 打包成功后自动调用；失败则 exit 1

**验收**

- [x] `scripts/verify-release-extensions.ps1`
- [x] `tests/test_release_extensions.py`
- [x] `make-release.ps1` 打包后自动校验

---

## P1 — 穿插（小 diff，不挡 P0）

| ID | 项 | 验收 |
|----|-----|------|
| P1-1 | Agent 事件常量 + `log_operation` helper | ✅ `agent_events.py` + `log_operation_from_meta`；`tests/agent/test_operations_log.py` |
| P1-2 | `agent.py` 第一阶段拆分（≤300 行模块） | ✅ `agent_tool_exec.py` mixin；`agent.py` ~500 行 |
| P1-3 | ~~更新/废弃 `OPTIMIZATION_PLAN.md`~~ | ✅ 已归档至 `docs/archive/`；活跃 backlog 以本文件为准 |
| P1-4 | **Referee 证据链**（强化 `goal_verifier`） | 见下 |
| P1-5 | **痛点记忆**（结构化踩坑库） | 见下 |
| P1-6 | **有限多 Agent 并发**（提思考效率，非无限群狼） | 见下 |

### P1-4 Referee 证据链

**背景**（Scream Code 启发）：Goal 完成须由「裁判」独立判断，不能只听主 Agent 自说「已完成」。

**现状**

- `goal_verifier.py` 已有：未完成 todo 拦截、checkpoint pending 拦截、可选 LLM 二审
- 缺：**可核对证据**（工具回执、交付物路径、微信发送回执）

**改动**

1. 收尾前收集本轮 **evidence bundle**：关键工具名 + 成功/失败 + 输出摘要 + artifact 路径
2. `verify_goal_complete`：有 open todo / pending 仍硬拦截；LLM 二审时传入 evidence，要求 `complete` 须与证据一致
3. 微信场景：无 `send_weixin_contact_message` 成功回执或未写入 `delivered/` 时，禁止宣称「已发送」
4. 设置项：`goal_verifier_evidence_required`（默认开）

**验收**

- [x] 待办未完成仍 block（回归现有测试）
- [x] 助手说「已完成」但无对应工具成功 / 文件不存在 → block + 中文 reason
- [x] `tests/brain/test_goal_verifier.py` 覆盖 evidence 路径

---

### P1-5 痛点记忆（结构化踩坑库）

**背景**（Scream Code Memo 启发）：记「用户踩过的坑」比泛偏好更有复用价值；检索用 tag + 关键词，后续可加向量。

**现状**

- `user_memory.py`：`remember_user_fact`，≤25 条平铺事实，偏偏好/习惯
- 无「场景 tag + 失败原因 + 修复动作」结构

**改动**

1. 扩展 fact schema（或 `pain_points.json`）：`{ tag, symptom, cause, fix, seen_at }`（tag 如 `api_key` / `weixin_send` / `ppt` / `path`）
2. 工具：`remember_pain_point` / 检索并入 `search_saved_memory`（tag 优先，再全文）
3. Agent 规则：同类错误第二次任务前主动 `search_saved_memory`
4. 上限与淘汰：如最多 40 条，LRU 或按 `seen_at` 合并重复 tag

**验收**

- [x] 写入后跨会话可读；同 tag 重复写入合并而非刷屏
- [x] `search_saved_memory("weixin_send")` 能命中对应痛点
- [x] `tests/agent/test_pain_points.py` 覆盖 schema 与上限

**非目标（P1）**：SQLite、embedding 双检索 — 留 P2 可选

---

### P1-6 有限多 Agent 并发（Bounded Multi-Agent）

**背景**（Scream Code 群狼模式启发）：多 Agent 并行可提高**思考与规划**效率；**不做**无限并发、不做常驻狼群进程。

**原则**

- **有上限**：单用户任务同时活跃子 Agent ≤ **2～3**（可配置 `max_sub_agents`，默认 2）
- **分工固定**：规划 / 调研 / 执行 等**角色模板**，非任意 spawn
- **主 Agent 仍唯一对外**：子 Agent 只产出结构化中间结果（plan、research notes、checklist），不直接调危险工具
- **与现有并行工具调用共存**：只读调研类可子 Agent；写盘/Shell/微信仍走主 Agent + 审批

**候选形态（v1.5 试点）**

```
用户复杂任务
    → 主 Agent 判定 needs_decomposition
    → Planner 子 Agent（1 次 LLM）：输出 steps + 依赖
    → 可选 Research 子 Agent（并行只读：list/search/browse，≤2 路）
    → 主 Agent 合并后执行工具
    → goal_verifier + evidence（P1-4）收尾
```

**改动**

1. `friday/sub_agents.py`（或 agent 子模块）：角色 prompt、并发池、超时、取消
2. 设置：`multi_agent_enabled`（默认关）、`max_sub_agents`（默认 2）
3. 观测：operations log 标记 `sub_agent:planner|research` 便于诊断

**验收**

- [x] 关闭时行为与现版完全一致（`tests/agent/test_sub_agents.py`）
- [ ] 开启后 3 步以上复杂任务：plan 质量可测（固定 eval case ≥1）
- [ ] 并发数超过上限时排队，不 spawn 第 4 个
- [ ] 子 Agent 无法调用 delete_file / run_powershell / 微信发送等 HIGH 风险工具

**非目标**：无限群狼、子 Agent 各带独立会话 UI、分布式 worker

---

## P2 — 质量门禁

| ID | 项 | 验收 |
|----|-----|------|
| P2-1 | 发版前凭据回归 | ✅ `make-release.ps1` build 前跑凭据 pytest |
| P2-2 | E2E 启动断言 bootstrap | ✅ `test_health.py` bundled_skills 断言 |
| P2-3 | 渐进 typecheck | ✅ `run-typecheck.cmd` 覆盖 server/bundled/health |

---

## P3 — 明确不做（除非产品需求变化）

- 全库 TypedDict
- ToolRegistry 架构重写
- 新写上下文压缩引擎
- 无需求的性能监控占位模块
- **无限并发群狼 / 常驻多 Agent 进程**（有限多 Agent 见 P1-6）
- Agent 全插件化运行时 / 微信独立进程（Phase 2，见 CEO 评审 Approach C）

---

## 建议发版顺序

1. **v1.4.9**（patch）：P0-1 + P0-2 + P0-3 + 回归测试
2. **v1.5.0**（minor，可选）：P1-1/P1-2 + **P1-4 Referee 证据链** + **P1-5 痛点记忆**
3. **v1.5.x / v1.6.0**（minor）：**P1-6 有限多 Agent**（默认关，试点 eval 通过后默认开）

---

## 参考

- CEO 评审：路线 A（交付优先），2026-06-18
- Scream Code 启发（2026-06-18）：Referee 证据链、痛点记忆、有限多 Agent（非群狼）
- 已修复勿重复：`server._lifespan` 后台 warmup（v1.4.8）、`context_assembler` 预算、`ToolRegistry` RiskLevel
