$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

function Remove-TreeSafe([string]$Path) {
    if (-not (Test-Path $Path)) { return }
    try {
        Remove-Item $Path -Recurse -Force -ErrorAction Stop
        Write-Host "  removed $Path/" -ForegroundColor Green
    } catch {
        Write-Host "  skipped $Path/ (files in use — close Friday.exe and rerun)" -ForegroundColor Yellow
    }
}

Write-Host "Cleaning build artifacts..." -ForegroundColor Cyan
Remove-TreeSafe "build"
Remove-TreeSafe "dist"

Write-Host "Cleaning __pycache__ (friday + tests)..." -ForegroundColor Cyan
Get-ChildItem -Path @("friday", "tests") -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Done. Rebuild: scripts/build.ps1" -ForegroundColor Green
