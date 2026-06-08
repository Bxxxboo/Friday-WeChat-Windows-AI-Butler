$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

. (Join-Path $PSScriptRoot "friday-dist.ps1")

$VersionLine = Select-String -Path "friday\version.py" -Pattern '__version__ = "(.+)"' | Select-Object -First 1
if (-not $VersionLine) { throw "Cannot read __version__ from friday/version.py" }
$Version = $VersionLine.Matches[0].Groups[1].Value
Write-Host "Release version: v$Version" -ForegroundColor Cyan

$DistApp = Get-FridayDistDir -Root $PWD
$Exe = Get-FridayExe -DistDir $DistApp

if (-not $Exe) {
    Write-Host "Building exe..." -ForegroundColor Yellow
    & (Join-Path $PWD "scripts\build.ps1")
    $Exe = Get-ChildItem $DistApp -Filter "*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $Exe) {
        throw "Build failed."
    }
}

$ReleaseRoot = Join-Path $PWD "release"
$GuideName = -join ([char]0x5B89, [char]0x88C5, [char]0x6559, [char]0x7A0B) + ".txt"
$ShortcutName = -join ([char]0x521B, [char]0x5EFA, [char]0x684C, [char]0x9762, [char]0x5FEB, [char]0x6377, [char]0x65B9, [char]0x5F0F) + ".ps1"
$ZipName = "Friday-Windows-v$Version.zip"
$LegacyZipName = "Friday-Windows.zip"

$Stage = Join-Path $ReleaseRoot "stage"
if (Test-Path $Stage) {
    Remove-Item $Stage -Recurse -Force
}
New-Item -ItemType Directory -Path $Stage -Force | Out-Null

Copy-Item (Join-Path $ReleaseRoot $GuideName) $Stage -Force
Copy-Item (Join-Path $ReleaseRoot $ShortcutName) $Stage -Force
$UnblockName = -join ([char]0x89E3, [char]0x9664, [char]0x9501, [char]0x5B9A) + ".ps1"
$UnblockScript = Join-Path $ReleaseRoot $UnblockName
if (Test-Path $UnblockScript) {
    Copy-Item $UnblockScript $Stage -Force
}
Copy-Item $DistApp (Join-Path $Stage "Friday") -Recurse -Force

Set-Content -Path (Join-Path $Stage "VERSION.txt") -Value "v$Version`nFriday-Windows-v$Version.zip" -Encoding UTF8

Write-Host "Unblocking staged files..." -ForegroundColor Cyan
Get-ChildItem -LiteralPath (Join-Path $Stage "Friday") -Recurse -ErrorAction SilentlyContinue |
    Unblock-File -ErrorAction SilentlyContinue

$FirstInstallName = -join ([char]0x9996, [char]0x6B21, [char]0x5B89, [char]0x88C5) + ".ps1"
$FirstInstallScript = Join-Path $ReleaseRoot $FirstInstallName
if (Test-Path $FirstInstallScript) {
    Copy-Item $FirstInstallScript $Stage -Force
}

$ZipPath = Join-Path $ReleaseRoot $ZipName
$LegacyZipPath = Join-Path $ReleaseRoot $LegacyZipName
foreach ($old in @($ZipPath, $LegacyZipPath)) {
    if (Test-Path $old) { Remove-Item $old -Force }
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($Stage, $ZipPath)
Copy-Item $ZipPath $LegacyZipPath -Force

Remove-Item $Stage -Recurse -Force

$sizeMb = [math]::Round((Get-Item $ZipPath).Length / 1MB, 1)
Write-Host ""
Write-Host "Done: $ZipPath (${sizeMb} MB)" -ForegroundColor Green
Write-Host "Legacy alias: $LegacyZipPath" -ForegroundColor DarkGray
