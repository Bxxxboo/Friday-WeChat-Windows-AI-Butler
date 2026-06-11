# 将 Agent 用 python.exe 复制为 FridayAgent.exe（任务管理器显示品牌化进程名）
# 用法:
#   powershell -ExecutionPolicy Bypass -File scripts\brand-agent-python.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\brand-agent-python.ps1 -Workspace "D:\docs\星期五"
#   powershell -ExecutionPolicy Bypass -File scripts\brand-agent-python.ps1 -EmbedOnly

param(
    [string]$Workspace = "",
    [switch]$EmbedOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".python-env\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = Join-Path $Root ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

$embedOnlyFlag = if ($EmbedOnly.IsPresent) { "1" } else { "0" }
$RunnerScript = Join-Path $PSScriptRoot "brand_agent_runner.py"

$result = & $Python $RunnerScript $Workspace $embedOnlyFlag | ConvertFrom-Json
Write-Host "Agent runner name: $($result.runner_name)" -ForegroundColor Cyan
if ($result.embed) {
    Write-Host "Embed branded: $($result.embed)" -ForegroundColor Green
} else {
    Write-Host "Embed: portable Python not found (run app once to download, or init Agent env)" -ForegroundColor Yellow
}
if (-not $EmbedOnly -and $Workspace -and $result.workspace) {
    Write-Host "Workspace branded: $($result.workspace)" -ForegroundColor Green
} elseif (-not $EmbedOnly -and $Workspace -and -not $result.workspace) {
    Write-Host "Workspace: .python-env not found under $Workspace" -ForegroundColor Yellow
}
