$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$workspace = $args[0]
if (-not $workspace) {
    $docs = [Environment]::GetFolderPath("MyDocuments")
    $workspace = Join-Path $docs "星期五"
}

Write-Host "工作区: $workspace" -ForegroundColor Cyan
$python = Join-Path $PWD ".python-env\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = Join-Path $PWD ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "请先运行 setup.ps1 安装星期五开发环境" -ForegroundColor Yellow
    exit 1
}

& "$python" -c "from friday.python_env import setup_agent_env; ok, msg = setup_agent_env(r'$workspace'); print(msg); raise SystemExit(0 if ok else 1)"
