$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Site = Join-Path $Root "source-repo"
$Port = 8766

Write-Host "Source repo site: http://127.0.0.1:$Port/" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop."

Set-Location $Site
python -m http.server $Port
