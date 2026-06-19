#Requires -Version 5.1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$lock = Join-Path $PWD "requirements-lock.txt"
if (-not (Test-Path $lock)) {
    Write-Error "requirements-lock.txt missing; run scripts\sync-requirements-lock.ps1"
    exit 1
}

$expected = @{}
Get-Content $lock | ForEach-Object {
    $line = $_.Trim()
    if ($line -match '^([A-Za-z0-9_-]+)==(.+)$') {
        $expected[$Matches[1].ToLower()] = $Matches[2]
    }
}

if ($expected.Count -lt 5) {
    Write-Error "requirements-lock.txt has too few pinned packages ($($expected.Count))"
    exit 1
}

Write-Host "requirements-lock.txt OK ($($expected.Count) pinned packages)"
