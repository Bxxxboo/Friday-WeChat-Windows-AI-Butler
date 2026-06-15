# Sync website/download.json and deploy Vercel + Gitee Pages mirror.
param(
    [string]$GiteeUser = "Bxxxboo",
    [string]$GiteeRepoName = "friday",
    [switch]$SkipWebsiteSync,
    [switch]$SkipVercel,
    [switch]$SkipGiteePages
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Resolve-EnvToken {
    param([string]$Name)
    $fromSession = ([Environment]::GetEnvironmentVariable($Name, "Process") | ForEach-Object { "$_".Trim() })
    if ($fromSession) { return $fromSession }
    foreach ($scope in @("User", "Machine")) {
        $fromProfile = ([Environment]::GetEnvironmentVariable($Name, $scope) | ForEach-Object { "$_".Trim() })
        if ($fromProfile) { return $fromProfile }
    }
    return ""
}

if (-not $SkipWebsiteSync) {
    Write-Host "=== Sync website/download.json ===" -ForegroundColor Cyan
    & (Join-Path $Root "scripts\sync-website-download.ps1")
} else {
    Write-Host "Skip website sync." -ForegroundColor Yellow
}

if (-not $SkipVercel) {
    Write-Host ""
    Write-Host "=== Deploy website (Vercel production) ===" -ForegroundColor Cyan
    $websiteDir = Join-Path $Root "website"
    Push-Location $websiteDir
    try {
        $deployOut = npx vercel deploy --prod --yes 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { throw "vercel deploy failed (exit $LASTEXITCODE)" }
        Write-Host $deployOut
        if ($deployOut -match '(https://website-[a-z0-9]+-bxxxboo-s-projects\.vercel\.app)') {
            $depUrl = $Matches[1]
            Write-Host "Aliasing fridayaiagent.vercel.app -> $depUrl" -ForegroundColor Cyan
            npx vercel alias set $depUrl fridayaiagent.vercel.app
            if ($LASTEXITCODE -ne 0) { throw "vercel alias failed (exit $LASTEXITCODE)" }
        } else {
            Write-Host "Could not parse deployment URL; run: npx vercel alias set <url> fridayaiagent.vercel.app" -ForegroundColor Yellow
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "Skip Vercel deploy." -ForegroundColor Yellow
}

if (-not $SkipGiteePages) {
    Write-Host ""
    Write-Host "=== Deploy website (Gitee Pages mirror) ===" -ForegroundColor Cyan
    $giteeToken = Resolve-EnvToken "GITEE_TOKEN"
    if ($giteeToken) { $env:GITEE_TOKEN = $giteeToken }
    if (-not $env:GITEE_TOKEN) {
        Write-Host "GITEE_TOKEN not set; skip Gitee Pages deploy." -ForegroundColor Yellow
    } else {
        & (Join-Path $Root "scripts\deploy-gitee-pages.ps1") -GiteeUser $GiteeUser -RepoName $GiteeRepoName
    }
} else {
    Write-Host "Skip Gitee Pages deploy." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Website deploy done." -ForegroundColor Green
Write-Host "  Vercel: https://fridayaiagent.vercel.app/download.json"
Write-Host "  Mirror: https://$GiteeUser.gitee.io/$GiteeRepoName"
