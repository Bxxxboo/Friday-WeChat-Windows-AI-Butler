# 本地 Cursor IDE：将 .cursor 目录联接至仓库内的 .friday（Gitee 上仅展示 .friday）
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$target = Join-Path $root ".friday"
$link = Join-Path $root ".cursor"

if (-not (Test-Path $target)) {
    throw "Missing .friday at $target"
}

if (Test-Path $link) {
    $item = Get-Item $link -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        Write-Host ".cursor already linked -> $($item.Target)" -ForegroundColor Yellow
        exit 0
    }
    throw ".cursor exists and is not a junction; remove or rename it first."
}

New-Item -ItemType Junction -Path $link -Target $target | Out-Null
Write-Host "Created junction: .cursor -> .friday" -ForegroundColor Green
