# Friday Windows 安装包（Inno Setup）

## 前置条件

1. [Inno Setup 6](https://jrsoftware.org/isinfo.php)  
   本机路径：`E:\Inno Setup 6\`（也可设置环境变量 `INNO_SETUP_DIR`）  
   简体中文语言文件已内置：`installer/Languages/ChineseSimplified.isl`（安装/卸载界面随系统语言自动切换）
2. 已构建 `dist/Friday/Friday.exe`：
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/build.ps1
   ```

## 构建

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build-installer.ps1
```

产出：`installer/output/Friday-Setup-{version}.exe`

发布时也会复制到 `release/Friday-Setup-{version}.exe`（与 ZIP 同级）。

## 目录

| 路径 | 说明 |
|------|------|
| `friday.iss` | Inno Setup 脚本 |
| `stage/Friday/` | 构建前由脚本从 `dist/Friday` 复制（git 忽略） |
| `output/` | 编译输出（git 忽略） |

详见 [docs/INSTALL-LAYOUT.md](../docs/INSTALL-LAYOUT.md)。
