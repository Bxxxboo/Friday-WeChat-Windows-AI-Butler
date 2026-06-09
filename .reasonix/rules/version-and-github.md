# 版本号与 Gitee / GitHub 双端同步

**适用：** 每次向远端发布

## 必须做

1. **bump 版本号**：`friday/version.py` + `scripts/version_info.py`
2. **同时 push** `origin`（GitHub）与 `gitee`（Gitee）
3. **发 Release**（`Friday-Windows.zip`）：Gitee 必发，GitHub 可选

## semver

| 级别 | 场景 |
|------|------|
| patch | bug 修复、UI 微调、脚本/CI |
| minor | 新功能、较大 UI（兼容） |
| major | 破坏性变更 |

## 一键发布

```powershell
$env:GITEE_TOKEN='令牌'
scripts\publish-release.cmd -Bump patch -GitHubRepoName Friday-Zero-barrier-DeepSeek-Agent-for-Windows
```

## 仅同步代码

```powershell
scripts\sync-remotes.cmd -Bump patch -GitHubRepoName Friday-Zero-barrier-DeepSeek-Agent-for-Windows
```

## 远端

| 远端 | 地址 |
|------|------|
| origin | github.com/Bxxxboo/Friday-Zero-barrier-DeepSeek-Agent-for-Windows |
| gitee | gitee.com/Bxxxboo/friday |

## 禁止

- 只 push GitHub 不 push Gitee
- 功能更新不改 `friday/version.py`
