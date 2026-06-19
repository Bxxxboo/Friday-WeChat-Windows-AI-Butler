#Requires -Version 5.1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$req = Join-Path $PWD "requirements.txt"
$lock = Join-Path $PWD "requirements-lock.txt"
if (-not (Test-Path $req)) { throw "requirements.txt not found" }

Write-Host "Generating requirements-lock.txt from requirements.txt ..."
$header = @(
    "# Pin runtime deps for reproducible release builds."
    "# Regenerate: scripts\sync-requirements-lock.ps1"
    "# Verify:     scripts\verify-requirements-lock.ps1"
    ""
    "-r requirements.txt"
    ""
)
$pip = Get-Command pip -ErrorAction SilentlyContinue
if (-not $pip) { throw "pip not found" }
$frozen = & pip freeze 2>$null | Where-Object { $_ -match '^[A-Za-z0-9_-]+==' }
if (-not $frozen) {
    Write-Host "Installing requirements.txt into current env before freeze ..."
    & pip install -q -r $req
    $frozen = & pip freeze | Where-Object { $_ -match '^[A-Za-z0-9_-]+==' }
}
($header + $frozen) | Set-Content -Path $lock -Encoding UTF8
Write-Host "Wrote $lock ($($frozen.Count) packages)"
