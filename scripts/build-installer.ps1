# Build Friday-Setup-{version}.exe (Inno Setup 6)
param(
    [switch]$SkipBuild,
    [string]$Root = ""
)

$ErrorActionPreference = "Stop"
if (-not $Root) {
    $Root = Split-Path -Parent $PSScriptRoot
}
Set-Location $Root

. (Join-Path $PSScriptRoot "friday-dist.ps1")

function Find-ISCC {
    $candidates = @(
        "E:\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    if ($env:INNO_SETUP_DIR) {
        $candidates = @((Join-Path $env:INNO_SETUP_DIR "ISCC.exe")) + $candidates
    }
    foreach ($path in $candidates) {
        if (Test-Path -LiteralPath $path) { return $path }
    }
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

$Iscc = Find-ISCC
if (-not $Iscc) {
    Write-Host ""
    Write-Host "Inno Setup 6 not found. Install from https://jrsoftware.org/isinfo.php" -ForegroundColor Yellow
    Write-Host "Stage dir is still at installer/stage for manual compile." -ForegroundColor Yellow
    exit 2
}

if (-not $SkipBuild) {
    $Exe = Get-FridayExe -DistDir (Get-FridayDistDir -Root $Root)
    $TargetVersion = Get-FridayVersion -Root $Root
    $needsBuild = -not $Exe
    if ($Exe -and $TargetVersion -ne "unknown") {
        $builtVersion = ($Exe.VersionInfo.ProductVersion -replace '\.0$', '')
        if ($builtVersion -ne $TargetVersion) { $needsBuild = $true }
    }
    if ($needsBuild) {
        Write-Host "Building dist first..." -ForegroundColor Yellow
        & (Join-Path $Root "scripts\build.ps1")
    }
}

& (Join-Path $PSScriptRoot "installer-prepare.ps1") -Root $Root

$version = Get-FridayVersion -Root $Root
$Iss = Join-Path $Root "installer\friday.iss"
$OutDir = Join-Path $Root "installer\output"
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

Write-Host "Compiling installer with ISCC..." -ForegroundColor Cyan
& $Iscc "/DMyAppVersion=$version" $Iss
if ($LASTEXITCODE -ne 0) {
    throw "ISCC failed with exit code $LASTEXITCODE"
}

$setupName = "Friday-Setup-$version.exe"
$built = Join-Path $OutDir $setupName
if (-not (Test-Path -LiteralPath $built)) {
    throw "Expected output not found: $built"
}

$releaseCopy = Join-Path (Join-Path $Root "release") $setupName
Copy-Item -LiteralPath $built -Destination $releaseCopy -Force

$sizeMb = [math]::Round((Get-Item -LiteralPath $built).Length / 1MB, 1)
Write-Host ""
Write-Host "Done: $built (${sizeMb} MB)" -ForegroundColor Green
Write-Host "Also: $releaseCopy" -ForegroundColor Green
