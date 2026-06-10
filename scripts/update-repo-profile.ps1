param(
    [switch]$SkipGithub,
    [switch]$SkipGitee
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Py = Join-Path $Root ".python-env\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

$Args = @("scripts\update_repo_profile.py")
if ($SkipGithub) { $Args += "--skip-github" }
if ($SkipGitee) { $Args += "--skip-gitee" }

& $Py @Args
