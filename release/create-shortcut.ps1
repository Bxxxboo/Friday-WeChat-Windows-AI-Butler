$ErrorActionPreference = "Stop"

$Root = Split-Path $PSScriptRoot -Parent
$RunPy = Join-Path $Root "run.py"
$Pythonw = Join-Path $Root ".python-env\Scripts\pythonw.exe"
$Python = Join-Path $Root ".python-env\Scripts\python.exe"

if (-not (Test-Path $RunPy)) {
    Write-Host "Missing: $RunPy" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $Pythonw)) {
    Write-Host "Run setup.ps1 in $Root first" -ForegroundColor Red
    exit 1
}

$CreateIcon = Join-Path $Root "scripts\create_icon.py"
if (Test-Path $CreateIcon) {
    if (Test-Path $Python) {
        & $Python $CreateIcon
    } else {
        python $CreateIcon
    }
}

$IconSrc = Join-Path $Root "assets\friday.ico"
if (-not (Test-Path $IconSrc)) {
    Write-Host "Missing icon: $IconSrc" -ForegroundColor Red
    exit 1
}

$AppDataFriday = Join-Path $env:APPDATA "Friday"
New-Item -ItemType Directory -Force -Path $AppDataFriday | Out-Null
$Icon = Join-Path $AppDataFriday "friday.ico"
Copy-Item -Path $IconSrc -Destination $Icon -Force
(Get-Item $Icon).LastWriteTime = Get-Date

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop ([char]0x661F + [char]0x671F + [char]0x4E94 + ".lnk")
$LegacyTestPath = Join-Path $Desktop ([char]0x661F + [char]0x671F + [char]0x4E94 + [char]0x6D4B + [char]0x8BD5 + [char]0x7248 + ".lnk")

$WshShell = New-Object -ComObject WScript.Shell
$testLabel = [char]0x6D4B + [char]0x8BD5 + [char]0x7248
$fridayLabel = [char]0x661F + [char]0x671F + [char]0x4E94

foreach ($old in @($ShortcutPath, $LegacyTestPath)) {
    if (Test-Path $old) {
        Remove-Item $old -Force
    }
}

Get-ChildItem $Desktop -Filter "*.lnk" -ErrorAction SilentlyContinue | ForEach-Object {
    $sc = $WshShell.CreateShortcut($_.FullName)
    $args = $sc.Arguments
    $targetsFriday =
        ($args -match [regex]::Escape($RunPy)) -or
        ($args -match 'Friday[\\/]run\.py') -or
        ($sc.Description -match 'Friday') -or
        ($_.BaseName -match $testLabel) -or
        ($_.BaseName -eq ($fridayLabel + $testLabel))
    if ($targetsFriday -and $_.FullName -ne $ShortcutPath) {
        Remove-Item $_.FullName -Force
        Write-Host "Removed legacy shortcut: $($_.Name)" -ForegroundColor Yellow
    }
}

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Pythonw
$Shortcut.Arguments = "`"$RunPy`""
$Shortcut.WorkingDirectory = $Root
$Shortcut.WindowStyle = 7
$Shortcut.IconLocation = "$Icon,0"
$desc = [char]0x661F + [char]0x671F + [char]0x4E94
$Shortcut.Description = "$desc ($Root)"
$Shortcut.Save()

# 刷新 Shell 图标缓存（否则桌面仍显示旧黑色图标）
$ie4u = Join-Path $env:SystemRoot "System32\ie4uinit.exe"
if (Test-Path $ie4u) {
    Start-Process -FilePath $ie4u -ArgumentList "-show" -WindowStyle Hidden
}

Write-Host "Icon: $Icon" -ForegroundColor Green
Write-Host "Shortcut: $ShortcutPath" -ForegroundColor Green
Write-Host "Root: $Root"
