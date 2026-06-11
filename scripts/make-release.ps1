$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

. (Join-Path $PSScriptRoot "friday-dist.ps1")

$DistApp = Get-FridayDistDir -Root $PWD
$Exe = Get-FridayExe -DistDir $DistApp

$VersionLine = Select-String -Path (Join-Path $PWD "friday\version.py") -Pattern '__version__ = "(.+)"' | Select-Object -First 1
$TargetVersion = if ($VersionLine) { $VersionLine.Matches[0].Groups[1].Value } else { "" }

$needsBuild = -not $Exe
if ($Exe -and $TargetVersion) {
    $builtVersion = ($Exe.VersionInfo.ProductVersion -replace '\.0$', '')
    if ($builtVersion -ne $TargetVersion) {
        Write-Host "Dist exe is v$builtVersion, need v$TargetVersion — rebuilding..." -ForegroundColor Yellow
        $needsBuild = $true
    }
}

if ($needsBuild) {
    Write-Host "Building exe..." -ForegroundColor Yellow
    & (Join-Path $PWD "scripts\build.ps1")
    $Exe = Get-FridayExe -DistDir (Get-FridayDistDir -Root $PWD)
    if (-not $Exe) {
        throw "Build failed."
    }
}

if (-not $TargetVersion) {
    $TargetVersion = Get-FridayVersion -Root $PWD
}

$ReleaseRoot = Join-Path $PWD "release"
$GuideName = -join ([char]0x5B89, [char]0x88C5, [char]0x6559, [char]0x7A0B) + ".txt"
$UnblockName = -join ([char]0x89E3, [char]0x9664, [char]0x9501, [char]0x5B9A) + ".ps1"
$SetupName = "Friday-Setup-$TargetVersion.exe"
$ZipName = "Friday-Windows-$TargetVersion.zip"
$UpdateZipName = "Friday-Update-$TargetVersion.zip"

# 先构建安装包，再组装发布 ZIP（内含 Setup.exe，供官网/浏览器下载）
$SetupPath = Join-Path $ReleaseRoot $SetupName
$BuildInstaller = Join-Path $PWD "scripts\build-installer.ps1"
if (Test-Path $BuildInstaller) {
    Write-Host ""
    Write-Host "Building Setup installer..." -ForegroundColor Cyan
    & $BuildInstaller -SkipBuild -Root $PWD
    if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $SetupPath)) {
        $setupMb = [math]::Round((Get-Item $SetupPath).Length / 1MB, 1)
        Write-Host "Done Setup: $SetupPath (${setupMb} MB)" -ForegroundColor Green
    } elseif ($LASTEXITCODE -eq 2) {
        Write-Host "Setup skipped (install Inno Setup 6 to build Friday-Setup-*.exe)" -ForegroundColor Yellow
    } else {
        Write-Host "Setup build failed (exit $LASTEXITCODE)" -ForegroundColor Yellow
    }
}

if (-not (Test-Path -LiteralPath $SetupPath)) {
    throw "Friday-Setup-$TargetVersion.exe not found. Install Inno Setup 6 and rerun make-release.ps1."
}

function New-ReleaseZip {
    param(
        [string]$Stage,
        [string]$ZipPath
    )
    if (Test-Path $Stage) {
        Remove-Item $Stage -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Stage -Force | Out-Null
    return @{
        Stage   = $Stage
        ZipPath = $ZipPath
    }
}

function Write-ReleaseZip {
    param(
        [string]$Stage,
        [string]$ZipPath
    )
    if (Test-Path $ZipPath) {
        Remove-Item $ZipPath -Force
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($Stage, $ZipPath)
    Remove-Item $Stage -Recurse -Force
    $sizeMb = [math]::Round((Get-Item $ZipPath).Length / 1MB, 1)
    Write-Host "Done ZIP: $ZipPath (${sizeMb} MB)" -ForegroundColor Green
}

# --- Friday-Windows：解压后运行 Setup 安装程序（官网默认下载）---
$WindowsStageRoot = Join-Path $ReleaseRoot "stage-windows"
if (-not $WindowsStageRoot) { throw "WindowsStageRoot is empty (ReleaseRoot=$ReleaseRoot)" }
New-ReleaseZip -Stage $WindowsStageRoot -ZipPath (Join-Path $ReleaseRoot $ZipName) | Out-Null

@(
    "Friday Windows $TargetVersion"
    "Build: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    "Installer: $SetupName"
) | Set-Content -Path (Join-Path $WindowsStageRoot "VERSION.txt") -Encoding UTF8

Copy-Item (Join-Path $ReleaseRoot $GuideName) $WindowsStageRoot -Force
Copy-Item $SetupPath (Join-Path $WindowsStageRoot $SetupName) -Force
$UnblockScript = Join-Path $ReleaseRoot $UnblockName
if (Test-Path $UnblockScript) {
    Copy-Item $UnblockScript $WindowsStageRoot -Force
}
# 兼容 1.2.x 应用内一键更新（旧版只拉 Friday-Windows.zip，须含 Friday\Friday.exe）
if (-not $ReleaseRoot) { throw "ReleaseRoot is empty before portable stage (PWD=$PWD)" }
$PortableStageDir = $ReleaseRoot + [System.IO.Path]::DirectorySeparatorChar + "stage-windows" + [System.IO.Path]::DirectorySeparatorChar + "Friday"
Write-Host ("Staging portable app -> {0}" -f $PortableStageDir) -ForegroundColor Cyan
New-Item -ItemType Directory -Path $PortableStageDir -Force | Out-Null
$portableSrc = $DistApp
$installerStage = [System.IO.Path]::Combine($PWD, "installer", "stage", "Friday")
if (Test-Path -LiteralPath ([System.IO.Path]::Combine($installerStage, "Friday.exe"))) {
    $portableSrc = $installerStage
}
Copy-Item -Path (Join-Path $portableSrc "*") -Destination $PortableStageDir -Recurse -Force
Write-Host "Unblocking staged Windows zip files..." -ForegroundColor Cyan
Get-ChildItem -LiteralPath $PortableStageDir -Recurse -ErrorAction SilentlyContinue |
    Unblock-File -ErrorAction SilentlyContinue

$portableExe = [System.IO.Path]::Combine($PortableStageDir, "Friday.exe")
if (-not (Test-Path -LiteralPath $portableExe)) {
    throw "Windows zip stage missing Friday.exe (src=$portableSrc). Re-run scripts\build.ps1 then make-release.ps1."
}

Write-Host ""
Write-Host "Packing $ZipName (Setup + portable for legacy updater)..." -ForegroundColor Cyan
Write-ReleaseZip -Stage $WindowsStageRoot -ZipPath (Join-Path $ReleaseRoot $ZipName)

# --- Friday-Update：便携目录，供应用内「一键更新」覆盖安装 ---
$UpdateStageRoot = Join-Path $ReleaseRoot "stage-update"
New-ReleaseZip -Stage $UpdateStageRoot -ZipPath (Join-Path $ReleaseRoot $UpdateZipName) | Out-Null

@(
    "Friday Update $TargetVersion"
    "Build: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    "For in-app auto-update only (contains Friday\Friday.exe)."
) | Set-Content -Path (Join-Path $UpdateStageRoot "VERSION.txt") -Encoding UTF8

$UpdatePortableDir = $ReleaseRoot + [System.IO.Path]::DirectorySeparatorChar + "stage-update" + [System.IO.Path]::DirectorySeparatorChar + "Friday"
New-Item -ItemType Directory -Path $UpdatePortableDir -Force | Out-Null
$updateSrc = if (Test-Path -LiteralPath ([System.IO.Path]::Combine($installerStage, "Friday.exe"))) { $installerStage } else { $DistApp }
Copy-Item -Path (Join-Path $updateSrc "*") -Destination $UpdatePortableDir -Recurse -Force
Write-Host "Unblocking staged update files..." -ForegroundColor Cyan
Get-ChildItem -LiteralPath $UpdatePortableDir -Recurse -ErrorAction SilentlyContinue |
    Unblock-File -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Packing $UpdateZipName (in-app updater)..." -ForegroundColor Cyan
Write-ReleaseZip -Stage $UpdateStageRoot -ZipPath (Join-Path $ReleaseRoot $UpdateZipName)

Write-Host ""
Write-Host "Release artifacts ready in $ReleaseRoot" -ForegroundColor Green
