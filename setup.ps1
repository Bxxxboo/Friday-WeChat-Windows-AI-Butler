$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Find-Python {
    $candidates = @(
        "python",
        "py",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
    )
    foreach ($cmd in $candidates) {
        try {
            if ($cmd -like "*\\*") {
                if (Test-Path $cmd) { return $cmd }
                continue
            }
            $resolved = Get-Command $cmd -ErrorAction Stop
            $version = & $resolved.Source --version 2>&1
            if ($version -match "Python 3\.(1[1-9]|[2-9][0-9])") {
                return $resolved.Source
            }
        } catch {
            continue
        }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Write-Host "未检测到 Python 3.11+。请先安装：" -ForegroundColor Yellow
    Write-Host "  winget install Python.Python.3.12"
    exit 1
}

Write-Host "使用 Python: $python"
& $python -m venv .venv
& .\.venv\Scripts\python -m pip install --upgrade pip
& .\.venv\Scripts\pip install -r requirements.txt

$workspace = [Environment]::GetFolderPath("MyDocuments")
if (-not (Test-Path $workspace)) {
    $workspace = Join-Path $env:USERPROFILE "Documents"
}
if (-not (Test-Path $workspace)) {
    New-Item -ItemType Directory -Path $workspace | Out-Null
}
Write-Host "建议默认文件夹: $workspace"

Write-Host "安装完成。启动命令：" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\python run.py"
Write-Host ""
Write-Host "可选：初始化 Agent Python 环境（工作区 .python-env）：" -ForegroundColor Cyan
Write-Host "  .\scripts\setup-python-env.ps1"
