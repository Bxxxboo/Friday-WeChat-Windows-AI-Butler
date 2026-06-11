# Friday Windows 安装目录规范

> 对应长期计划 **M2**。程序安装位置与用户数据分离。

## 两种分发形态

| 形态 | 获取方式 | 程序目录 | 适用人群 |
|------|----------|----------|----------|
| **安装包（推荐）** | `Friday-Setup-{version}.exe` | `%LOCALAPPDATA%\Programs\Friday\` | 普通用户 |
| **ZIP 绿色版（进阶）** | `Friday-Windows-{version}.zip` | 用户自选（如 `D:\Friday\`） | 开发者 / 便携 |

两种形态共用同一套**用户数据目录**，换机或覆盖安装不会丢设置（除非用户主动删除）。

## 目录约定

### 程序目录（可卸载、可被一键更新覆盖）

```
%LOCALAPPDATA%\Programs\Friday\     ← Inno Setup 默认 {app}
├── Friday.exe                      ← 主进程（任务管理器显示「星期五」）
├── FridayAgent.exe                 ← Agent 子进程（同目录 Scripts 或 embed 复制）
├── app.ico
├── _internal\                      ← PyInstaller onedir 依赖
└── …
```

- 代码中通过 `sys.executable` 的父目录定位：`friday.update_installer.app_install_dir()`
- 常量：`friday.paths.default_install_dir()`（未安装时的推荐路径）

### 用户数据目录（卸载默认保留）

```
%APPDATA%\Friday\
├── settings.json
├── sessions\
├── friday.log
├── updates\                        ← 一键更新临时文件
├── crashes\                        ← M4 崩溃日志（规划）
└── …
```

- 代码：`friday.paths.get_appdata_dir()`
- **卸载程序不删除此目录**（Inno Setup 仅移除 `{app}`）

### 更新备份目录（一键更新前创建）

```
{程序父目录}\Friday.bak\            ← 与 Friday\ 同级，覆盖更新前整目录备份
```

- 代码：`friday.update_installer.install_backup_dir()`
- 用于 M2.7 备份与 M2.8 失败回滚

## 与现有模块对齐

| 模块 | 行为 |
|------|------|
| `friday/autostart.py` | 打包版自启指向 `Friday.exe`，禁止 fallback `pythonw` |
| `friday/update_installer.py` | 仅 `frozen` 模式；替换 `app_install_dir()` 内容 |
| `scripts/make-release.ps1` | 产出 ZIP；集成后同时产出 Setup |
| `installer/friday.iss` | 安装到 `{localappdata}\Programs\Friday`，安装后 Unblock |

## 安装器用户可见项

- 开始菜单：**星期五**
- 可选任务：创建桌面快捷方式
- 安装完成：可选立即启动
- 卸载：控制面板 / 设置 → 应用 → 卸载「星期五」

## 验证清单

```powershell
# 安装后
Test-Path "$env:LOCALAPPDATA\Programs\Friday\Friday.exe"
# 开始菜单可启动；任务管理器主进程为 Friday

# 用户数据独立
Test-Path "$env:APPDATA\Friday\settings.json"   # 升级后仍存在

# ZIP 用户仍可将 Friday 文件夹解压到任意路径，行为与安装版一致（除卸载入口）
```
