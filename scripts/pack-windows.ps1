# Pack Friday Windows zip for local testing / other PCs
# Usage:
#   scripts\pack-windows.ps1
#   scripts\pack-windows.ps1 -SkipBuild
#   scripts\pack-windows.ps1 -OpenFolder

param(
    [switch]$SkipBuild,
    [switch]$OpenFolder
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

. (Join-Path $PSScriptRoot "friday-dist.ps1")

function Get-FridayVersion {
    $versionFile = Join-Path $Root "friday\version.py"
    if (-not (Test-Path $versionFile)) { return "unknown" }
    $line = Get-Content $versionFile -Encoding UTF8 | Where-Object { $_ -match '__version__' } | Select-Object -First 1
    if ($line -match '__version__\s*=\s*"([^"]+)"') { return $Matches[1] }
    return "unknown"
}

$version = Get-FridayVersion
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Friday Windows pack  v$version" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (-not $SkipBuild) {
    Write-Host "[1/2] PyInstaller build (1-3 min)..." -ForegroundColor Yellow
    & (Join-Path $Root "scripts\build.ps1")
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "build.ps1 failed with exit code $LASTEXITCODE"
    }
} else {
    Write-Host "[1/2] Skip build (-SkipBuild)" -ForegroundColor DarkGray
    $dist = Get-FridayDistDir -Root $Root
    if (-not (Get-FridayExe -DistDir $dist)) {
        throw "No exe in dist. Run build.ps1 first or drop -SkipBuild."
    }
}

Write-Host "[2/2] Create release/Friday-Windows.zip ..." -ForegroundColor Yellow
& (Join-Path $Root "scripts\make-release.ps1")
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    throw "make-release.ps1 failed with exit code $LASTEXITCODE"
}

$zip = Join-Path $Root "release\Friday-Windows.zip"
if (-not (Test-Path $zip)) {
    throw "Zip not created: $zip"
}

$sizeMb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  Zip:  $zip" -ForegroundColor Green
Write-Host "  Size: ${sizeMb} MB" -ForegroundColor Green
Write-Host ""
Write-Host "On another PC: unzip, run release scripts, then Friday\*.exe" -ForegroundColor Cyan
Write-Host ""

if ($OpenFolder) {
    Start-Process explorer.exe (Split-Path $zip -Parent)
}
