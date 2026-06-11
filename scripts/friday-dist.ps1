$ErrorActionPreference = "Stop"

function Get-FridayDistDir {
    param([string]$Root)
    $ascii = Join-Path (Join-Path $Root "dist") "Friday"
    if (Test-Path $ascii) { return $ascii }
    $legacy = Join-Path (Join-Path $Root "dist") (-join ([char]0x661F, [char]0x671F, [char]0x4E94))
    if (Test-Path $legacy) { return $legacy }
    return $ascii
}

function Get-FridayExe {
    param([string]$DistDir)
    $preferred = Join-Path $DistDir "Friday.exe"
    if (Test-Path -LiteralPath $preferred) {
        return Get-Item -LiteralPath $preferred
    }
    $legacyName = -join ([char]0x661F, [char]0x671F, [char]0x4E94) + ".exe"
    $legacy = Join-Path $DistDir $legacyName
    if (Test-Path -LiteralPath $legacy) {
        return Get-Item -LiteralPath $legacy
    }
    return Get-ChildItem $DistDir -Filter "*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
}

function Get-FridayVersion {
    param([string]$Root = (Get-Location).Path)
    $versionFile = Join-Path $Root "friday\version.py"
    if (-not (Test-Path $versionFile)) { return "unknown" }
    $line = Get-Content $versionFile -Encoding UTF8 | Where-Object { $_ -match '__version__' } | Select-Object -First 1
    if ($line -match '__version__\s*=\s*"([^"]+)"') { return $Matches[1] }
    return "unknown"
}

function Get-FridayReleaseZipName {
    param([string]$Root = (Get-Location).Path)
    $v = Get-FridayVersion -Root $Root
    return "Friday-Windows-$v.zip"
}

function Get-FridayReleaseZipPath {
    param([string]$Root = (Get-Location).Path)
    Join-Path (Join-Path $Root "release") (Get-FridayReleaseZipName -Root $Root)
}
