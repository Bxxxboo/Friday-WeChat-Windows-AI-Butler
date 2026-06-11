# 将 dist/Friday 复制到 installer/stage/Friday，供 Inno Setup 打包
param(
    [string]$Root = ""
)

$ErrorActionPreference = "Stop"
if (-not $Root) {
    $Root = Split-Path -Parent $PSScriptRoot
}

. (Join-Path $PSScriptRoot "friday-dist.ps1")

$DistApp = Get-FridayDistDir -Root $Root
$Exe = Get-FridayExe -DistDir $DistApp
if (-not $Exe) {
    throw "未找到 dist/Friday/Friday.exe，请先运行 scripts/build.ps1"
}

$StageFriday = Join-Path $Root "installer\stage\Friday"
if (Test-Path (Join-Path $Root "installer\stage")) {
    Remove-Item (Join-Path $Root "installer\stage") -Recurse -Force
}
New-Item -ItemType Directory -Path $StageFriday -Force | Out-Null

Write-Host "Staging dist -> installer/stage/Friday ..." -ForegroundColor Cyan
Copy-Item -Path $DistApp\* -Destination $StageFriday -Recurse -Force

Write-Host "Unblocking staged files..." -ForegroundColor Cyan
Get-ChildItem -LiteralPath $StageFriday -Recurse -ErrorAction SilentlyContinue |
    Unblock-File -ErrorAction SilentlyContinue

$iconSrc = Join-Path $Root "assets\friday.ico"
$iconDst = Join-Path $StageFriday "app.ico"
if ((Test-Path $iconSrc) -and -not (Test-Path $iconDst)) {
    Copy-Item $iconSrc $iconDst -Force
}

$version = Get-FridayVersion -Root $Root
Write-Host "Staged v$version ($($Exe.Length) bytes exe)" -ForegroundColor Green
