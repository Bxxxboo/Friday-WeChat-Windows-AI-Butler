$ErrorActionPreference = "Stop"

$Root = Split-Path $PSScriptRoot -Parent
$RunPy = Join-Path $Root "run.py"
$Pythonw = Join-Path $Root ".python-env\Scripts\pythonw.exe"

if (-not (Test-Path $RunPy)) {
    Write-Host "Missing: $RunPy" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $Pythonw)) {
    Write-Host "Run setup.ps1 in $Root first" -ForegroundColor Red
    exit 1
}

$Icon = Join-Path $Root "assets\friday.ico"
if (-not (Test-Path $Icon)) {
    $Icon = $Pythonw
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop ([char]0x661F + [char]0x671F + [char]0x4E94 + ".lnk")
$LegacyTestPath = Join-Path $Desktop ([char]0x661F + [char]0x671F + [char]0x4E94 + [char]0x6D4B + [char]0x8BD5 + [char]0x7248 + ".lnk")

$WshShell = New-Object -ComObject WScript.Shell
$testLabel = [char]0x6D4B + [char]0x8BD5 + [char]0x7248   # 测试版
$fridayLabel = [char]0x661F + [char]0x671F + [char]0x4E94 # 星期五

foreach ($old in @($ShortcutPath, $LegacyTestPath)) {
    if (Test-Path $old) {
        Remove-Item $old -Force
    }
}

# Remove any other desktop shortcut that still launches this install (e.g. renamed 测试版).
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

Write-Host "Shortcut: $ShortcutPath" -ForegroundColor Green
Write-Host "Root: $Root"
