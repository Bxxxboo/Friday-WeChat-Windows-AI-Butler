param(
    [string]$Version = "",
    [ValidateSet("", "patch", "minor", "major")]
    [string]$Bump = "",
    [string]$RepoOwner = "Bxxxboo",
    [string]$GitHubRepoName = "Friday-WeChat-Windows-AI-Butler",
    [string]$GiteeUser = "Bxxxboo",
    [string]$GiteeRepoName = "friday",
    [switch]$SkipBuild,
    [switch]$SkipGithubRelease,
    [switch]$SkipGiteeRelease,
    [switch]$SkipVercel,
    [switch]$SkipGiteePages,
    [switch]$SkipWebsiteSync
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not $Version -and -not $Bump) {
    throw "Specify -Version 1.2.3 or -Bump patch|minor|major"
}
if ($Version -and $Bump) {
    throw "Use either -Version or -Bump, not both"
}

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

$giteeToken = Resolve-EnvToken "GITEE_TOKEN"
if ($giteeToken) { $env:GITEE_TOKEN = $giteeToken }

$githubToken = Resolve-EnvToken "GITHUB_TOKEN"
if ($githubToken) { $env:GITHUB_TOKEN = $githubToken }

Write-Host "=== Friday full release ===" -ForegroundColor Cyan

Write-Host ""
Write-Host "=== 1/5 Bump version ===" -ForegroundColor Cyan
if ($Version) {
    & (Join-Path $Root "scripts\bump-version.ps1") -Set $Version
} else {
    & (Join-Path $Root "scripts\bump-version.ps1") -Part $Bump
}

$VersionLine = Select-String -Path (Join-Path $Root "friday\version.py") -Pattern '__version__ = "(.+)"' | Select-Object -First 1
if (-not $VersionLine) { throw "Cannot read __version__ from friday/version.py" }
$TargetVersion = $VersionLine.Matches[0].Groups[1].Value
Write-Host "Target: v$TargetVersion" -ForegroundColor Green

if (-not $SkipWebsiteSync) {
    Write-Host ""
    Write-Host "=== 2/5 Sync website/download.json ===" -ForegroundColor Cyan
    & (Join-Path $Root "scripts\sync-website-download.ps1")
} else {
    Write-Host "Skip website sync." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 3/5 Git sync (GitHub + Gitee) ===" -ForegroundColor Cyan
$syncArgs = @{
    RepoOwner     = $RepoOwner
    GiteeUser     = $GiteeUser
    GiteeRepoName = $GiteeRepoName
    GitHubRepoName = $GitHubRepoName
    CommitMessage = "chore: release v$TargetVersion"
}
& (Join-Path $Root "scripts\sync-remotes.ps1") @syncArgs

if (-not $SkipGiteeRelease) {
    Write-Host ""
    Write-Host "=== 4/5 Gitee Release ===" -ForegroundColor Cyan
    if (-not $env:GITEE_TOKEN) {
        throw "GITEE_TOKEN not set. Add to Windows User environment variables."
    }
    $giteeArgs = @{ GiteeUser = $GiteeUser; RepoName = $GiteeRepoName }
    if ($SkipBuild) { $giteeArgs.SkipBuild = $true }
    & (Join-Path $Root "scripts\publish-gitee-release.ps1") @giteeArgs
} else {
    Write-Host "Skip Gitee release." -ForegroundColor Yellow
}

if (-not $SkipGithubRelease) {
    Write-Host ""
    Write-Host "=== 5/5 GitHub Release ===" -ForegroundColor Cyan
    # Gitee 步骤已构建时勿重复打包
    $ghSkipBuild = $SkipBuild -or (-not $SkipGiteeRelease)
    if (-not (Get-Command gh -ErrorAction SilentlyContinue) -and -not $env:GITHUB_TOKEN) {
        Write-Host "gh CLI and GITHUB_TOKEN unavailable; skip GitHub Release." -ForegroundColor Yellow
    } else {
        $ghArgs = @{
            RepoOwner = $RepoOwner
            RepoName  = $GitHubRepoName
        }
        if ($ghSkipBuild) { $ghArgs.SkipBuild = $true }
        & (Join-Path $Root "scripts\publish-github-release.ps1") @ghArgs
    }
} else {
    Write-Host "Skip GitHub release." -ForegroundColor Yellow
}

if (-not $SkipVercel -or -not $SkipGiteePages) {
    Write-Host ""
    Write-Host "=== Deploy website ===" -ForegroundColor Cyan
    $webArgs = @{
        GiteeUser     = $GiteeUser
        GiteeRepoName = $GiteeRepoName
        SkipWebsiteSync = $true
    }
    if ($SkipVercel) { $webArgs.SkipVercel = $true }
    if ($SkipGiteePages) { $webArgs.SkipGiteePages = $true }
    & (Join-Path $Root "scripts\deploy-website.ps1") @webArgs
} else {
    Write-Host "Skip website deploy (Vercel + Gitee Pages)." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Full release complete: v$TargetVersion ===" -ForegroundColor Green
Write-Host "  Gitee:   https://gitee.com/$GiteeUser/$GiteeRepoName/releases/tag/v$TargetVersion"
Write-Host "  GitHub:  https://github.com/$RepoOwner/$GitHubRepoName/releases/tag/v$TargetVersion"
Write-Host "  Website: https://fridayaiagent.vercel.app/download.json"
Write-Host "  Mirror:  https://$GiteeUser.gitee.io/$GiteeRepoName"
