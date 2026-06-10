---
name: surgical-bugfix
description: >-
  Fix bugs with minimal blast radius—scope lock, regression checks, and no
  drive-by refactors. Use when fixing bugs, debugging regressions, touching
  shared settings/credentials/merge logic, or when the user says 改错、串台、
  改A坏B、修bug别动别的模块、surgical bugfix.
---

# 外科手术式 Bug 修复

**目标**：只修报告里的 bug，不引入新 bug。改 A 不能坏 B。

与 [karpathy-guidelines](../karpathy-guidelines/SKILL.md) 配合：本 skill 补充 **范围锁定、共享模块、回归验证** 的操作清单。

---

## 0. 开工前三问（必须写出来）

1. **根因在哪条路径？**（例：保存 settings / 测试连接 / 微信 inbound / 生图 probe）
2. **允许改哪些文件？** 列出 ≤5 个；超出需向用户说明理由
3. **成功标准是什么？** 可运行的验证命令 + 预期结果

未答完不开刀。

---

## 1. 范围锁定（Scope Lock）

### 允许

- 与根因直接相关的函数/分支
- 为该 bug 新增的 **最小** 测试
- 为修 **自己造成的** 孤儿 import/变量做清理

### 禁止（除非用户明确要求）

- 顺手重构、重命名、格式化相邻代码
- 「顺便优化」UI、错误文案、日志级别
- 在修微信时改 credentials；在修生图时改 llm_profiles
- 一次 PR 混多个 unrelated 修复
- 未验证的「通用改进」（新 helper、新抽象、新配置项）

### 共享模块改动 = 高风险

改动下列文件时，**默认视为跨模块**，必须做第 3 节回归矩阵：

| 模块 | 文件 | 为何危险 |
|------|------|----------|
| 凭据读写 | `friday/credentials_store.py` | 保存/加载 Key；影响 LLM/视觉/生图全部 API |
| 设置合并 | `friday/storage.py` `merge_settings` / `load_settings` / `save_settings` | 空 Key 保留、profile 同步 |
| LLM profile | `friday/llm_profiles.py` | 切换服务商、Key 对齐 |
| 分类 profile | `friday/category_profiles.py` | 视觉/生图 Key 与服务商 |
| 设置 API | `friday/server.py` `_merge_payload`、PUT/POST test | 前端测试与保存共用合并逻辑 |
| 连通性探测 | `friday/api_connect.py` | 状态栏 + 测试连接 + 诊断 |

**规则**：若根因在 A 模块，却「只有改 B 模块才方便」→ 先停，说明 tradeoff，优先在 A 内修。

---

## 2. 修复工作流

```
1. 复现 → 写失败测试或最小脚本（先红）
2. 读调用链：谁调用被改函数？改签名/语义会影响谁？
3. 最小 diff 修根因（通常 ≤30 行；超过需解释）
4. 跑回归矩阵（第 3 节）
5. 向用户说明：改了什么、没改什么、如何验证
```

### 读调用链（必做）

改函数 `F` 前：

```bash
# 在仓库根目录
rg "F\(" friday web tests
```

对 **语义变更**（不仅是 bug 行）：列出至少 2 个调用方，确认行为仍正确。

### 共享逻辑修改检查单

动到 **保存/合并/凭据** 时，逐条确认：

- [ ] **新 Key 写入**：`save_settings` 后 `load_settings()` 读回的值 = 刚写入的值（非旧凭据）
- [ ] **空 Key 保留**：仅 `api_key` 为空时保留旧值；**非空必须覆盖**
- [ ] **load 与 save 对称**：`preserve_empty_*` 只填空，不能 `apply_secrets` 全覆盖
- [ ] **切换服务商**：`merge_*_settings` 换 provider 且无新 Key 时，应 `switch_*_profile`
- [ ] **测试路径 = 运行路径**：`/api/settings/test*` 与 Agent/微信 用同一套 `_merge_payload` / `load_settings`

---

## 3. 回归测试矩阵

### 3.1 必跑（改动涉及 settings/credentials/profile 时）

```powershell
cd e:\Friday
python -m pytest tests/api/test_credentials_store.py tests/providers/test_llm_profiles.py tests/providers/test_category_profiles.py -q
```

### 3.2 按域追加

| 你动到的域 | 追加测试 |
|------------|----------|
| 微信 | `tests/weixin/` |
| 生图/状态栏 | `tests/providers/test_image_gen.py` `tests/platform/test_api_connect.py` |
| 大模型/Brain | `tests/agent/test_brain.py` `tests/platform/test_api_connect.py` |
| 设置 API | `tests/api/test_settings_test.py` |

### 3.3 手工烟雾（credentials/merge 改动后）

```powershell
python -c "
from friday.storage import load_settings, save_settings, merge_settings, UserSettings
b = load_settings()
new = 'sk-' + 'x'*40 + 'END1'
save_settings(merge_settings(b, {'api_key': new, 'llm_provider': b.llm_provider or 'deepseek'}))
a = load_settings()
assert a.api_key.endswith('END1'), f'Key not saved: {a.api_key[-8:]}'
save_settings(b)
print('credentials roundtrip OK')
"
```

失败 = **禁止** 告诉用户「已修好」。

---

## 4. 反模式（本仓库真实案例）

### ❌ 修微信桥接时改 `apply_secrets_to_settings_data` 全覆盖

- **现象**：用户粘贴新 MiMo Key 点保存，界面仍显示旧 Key；测试永远 401
- **根因**：`preserve_empty_secrets_in_settings` 误用「凭据库覆盖全部字段」而非「仅填空字段」
- **教训**：改 save 路径必须跑 `test_save_replaces_existing_key_when_credentials_present`

### ❌ 修生图 profile 时改 `merge_settings`  early return 不跑空 Key 保留

- **现象**：切换火山方舟后用了 sk- Key
- **教训**：provider 切换 + 空 Key → 必须 `switch_*_profile`

### ❌ 修连通性时改 `api_ready` 语义却不改 UI

- **现象**：显示「API 已就绪」但测试失败
- **教训**：改 `api_ready` / status hint 时检查 `web/settings.js` `updateApiStatus`

---

## 5. 完成定义（DoD）

全部满足才可收尾：

- [ ] diff 中每行能指向用户 bug 或对应测试
- [ ] 新增/更新测试覆盖根因（非仅 happy path）
- [ ] 第 3 节矩阵已跑且通过
- [ ] 未改 scope 外文件（或已在回复中说明原因）
- [ ] 回复含：**根因一句话、改动文件列表、验证命令**

---

## 6. 对用户回复模板

```markdown
## 根因
[一条]

## 改动范围
- `path/to/file.py`：[为何动它]

## 未改动
- [刻意没碰的模块]

## 请你验证
1. ...
2. 命令：`pytest ...`
```

---

## 7. 何时停下来问用户

- 根因可能在 ≥2 个子系统（凭据 vs 前端 vs 桥接）
- 修复需要改共享模块且回归测试不存在
- 「顺便修」会发现另一明显 bug——**先报，不 silent fix**
