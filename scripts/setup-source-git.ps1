$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Git = "C:\Program Files\Git\bin\git.exe"
if (-not (Test-Path $Git)) {
    $Git = (Get-Command git -ErrorAction SilentlyContinue).Source
}
if (-not $Git) { throw "Git not found. Install from https://git-scm.com/download/win" }

if (-not (Test-Path ".git")) {
    & $Git init -b main
}

& $Git add -A
$status = & $Git status --porcelain
if ($status) {
    & $Git commit -m "chore: Friday source repository for GitHub import"
    Write-Host "Git commit created." -ForegroundColor Green
} else {
    Write-Host "Working tree clean, skip commit." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next: push to Gitee for import URL" -ForegroundColor Cyan
Write-Host "  powershell -File scripts/push-gitee-source.ps1 -GiteeUser YOUR_GITEE_USERNAME"
