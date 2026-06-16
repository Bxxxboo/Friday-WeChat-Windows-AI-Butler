$ErrorActionPreference = "Stop"
if (-not $PSScriptRoot) {
    throw "make-release.ps1 must be invoked with -File (PSScriptRoot missing)"
}
$FridayRepo = (Get-Item -LiteralPath $PSScriptRoot).Parent.FullName
Set-Location -LiteralPath $FridayRepo

. (Join-Path $PSScriptRoot "friday-dist.ps1")

$PptSkillMarker = [System.IO.Path]::Combine($FridayRepo, "extensions", "ppt-master", "scripts", "svg_to_pptx.py")
if (-not (Test-Path -LiteralPath $PptSkillMarker)) {
    $SyncPpt = Join-Path $FridayRepo "scripts\sync_ppt_master_skill.ps1"
    if (-not (Test-Path -LiteralPath $SyncPpt)) {
        throw "ppt-master skill missing and sync script not found: $SyncPpt"
    }
    Write-Host "Syncing ppt-master skill (first-time / missing)..." -ForegroundColor Cyan
    & $SyncPpt
    if (-not (Test-Path -LiteralPath $PptSkillMarker)) {
        throw "ppt-master skill sync failed: $PptSkillMarker missing"
    }
}

$DistApp = Get-FridayDistDir -Root $FridayRepo
$Exe = Get-FridayExe -DistDir $DistApp

$VersionLine = Select-String -Path (Join-Path $FridayRepo "friday\version.py") -Pattern '__version__ = "(.+)"' | Select-Object -First 1
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
    & (Join-Path $FridayRepo "scripts\build.ps1")
    $Exe = Get-FridayExe -DistDir (Get-FridayDistDir -Root $FridayRepo)
    if (-not $Exe) {
        throw "Build failed."
    }
}

if (-not $TargetVersion) {
    $TargetVersion = Get-FridayVersion -Root $FridayRepo
}

$ReleaseRoot = Join-Path $FridayRepo "release"
$SetupName = "Friday-Setup-$TargetVersion.exe"
$ZipName = "Friday-Windows-$TargetVersion.zip"
$UpdateZipName = "Friday-Update-$TargetVersion.zip"

# 先构建安装包，再组装发布 ZIP（内含 Setup.exe，供官网/浏览器下载）
$SetupPath = Join-Path $ReleaseRoot $SetupName
$BuildInstaller = Join-Path $FridayRepo "scripts\build-installer.ps1"
if (Test-Path $BuildInstaller) {
    Write-Host ""
    Write-Host "Building Setup installer..." -ForegroundColor Cyan
    & $BuildInstaller -SkipBuild -Root $FridayRepo
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

Copy-Item $SetupPath (Join-Path $WindowsStageRoot $SetupName) -Force
# 注意：Gitee Release 单附件约 100MB 上限，Windows ZIP 仅含 Setup（~64MB）。
# 应用内一键更新请拉取 Friday-Update.zip（1.3+ 优先）；1.2.x 请手动解压后运行 Setup。
Write-Host ""
Write-Host "Packing $ZipName (Setup installer for download)..." -ForegroundColor Cyan
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

# --- SHA256 清单（M3.3）---
$SumsPath = Join-Path $ReleaseRoot "SHA256SUMS.txt"
$sumLines = @(
    "# Friday v$TargetVersion — SHA256"
    "# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
)
foreach ($artifact in @(
    @{ Path = $SetupPath; Name = $SetupName }
    @{ Path = (Join-Path $ReleaseRoot $ZipName); Name = $ZipName }
    @{ Path = (Join-Path $ReleaseRoot $UpdateZipName); Name = $UpdateZipName }
)) {
    if (-not (Test-Path -LiteralPath $artifact.Path)) { continue }
    $hash = (Get-FileHash -LiteralPath $artifact.Path -Algorithm SHA256).Hash.ToLowerInvariant()
    $sumLines += "$hash  $($artifact.Name)"
}
$sumLines | Set-Content -Path $SumsPath -Encoding UTF8
Write-Host "SHA256SUMS.txt written ($SumsPath)" -ForegroundColor Green

Write-Host ""
Write-Host "Release artifacts ready in $ReleaseRoot" -ForegroundColor Green
