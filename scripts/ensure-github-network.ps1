# GitHub 发布网络：直连不可达时自动启用本地代理（git push / API / Release 上传共用）。
# 用法：. "$PSScriptRoot\ensure-github-network.ps1"; Enable-FridayGithubNetwork

$script:FridayGithubProxyCandidates = @(
    { $env:FRIDAY_HTTPS_PROXY },
    { $env:HTTPS_PROXY },
    { "http://127.0.0.1:7897" },
    { "http://127.0.0.1:7890" }
)

function Get-FridayProxyUrl {
    param([string]$Candidate)
    $raw = ($Candidate | ForEach-Object { "$_".Trim() })
    if (-not $raw) { return "" }
    if ($raw -match '^https?://') { return $raw }
    return "http://$raw"
}

function Test-FridayGithubReachable {
    param([string]$ProxyUrl = "")
    $prevHttp = $env:HTTP_PROXY
    $prevHttps = $env:HTTPS_PROXY
    try {
        if ($ProxyUrl) {
            $env:HTTP_PROXY = $ProxyUrl
            $env:HTTPS_PROXY = $ProxyUrl
        } else {
            Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue
            Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue
        }
        $out = & curl.exe -sI --connect-timeout 8 https://github.com 2>$null | Select-Object -First 1
        return ($out -match '^HTTP/\S+\s+200')
    } finally {
        if ($prevHttp) { $env:HTTP_PROXY = $prevHttp } else { Remove-Item Env:HTTP_PROXY -ErrorAction SilentlyContinue }
        if ($prevHttps) { $env:HTTPS_PROXY = $prevHttps } else { Remove-Item Env:HTTPS_PROXY -ErrorAction SilentlyContinue }
    }
}

function Enable-FridayGithubNetwork {
    param([switch]$Quiet)
    if (Test-FridayGithubReachable) {
        if (-not $Quiet) {
            Write-Host "GitHub reachable (direct)." -ForegroundColor DarkGray
        }
        return ""
    }

    foreach ($getter in $script:FridayGithubProxyCandidates) {
        $proxy = Get-FridayProxyUrl -Candidate (& $getter)
        if (-not $proxy) { continue }
        if (Test-FridayGithubReachable -ProxyUrl $proxy) {
            $env:HTTP_PROXY = $proxy
            $env:HTTPS_PROXY = $proxy
            if (-not $Quiet) {
                Write-Host "GitHub via proxy: $proxy" -ForegroundColor Yellow
            }
            return $proxy
        }
    }

    throw 'GitHub unreachable (direct and common local proxies failed). Set FRIDAY_HTTPS_PROXY, enable VPN, then re-run sync-remotes or publish-release. Do not claim release complete if only Gitee was pushed.'
}

function Assert-FridayRemotesAligned {
    param(
        [string]$Git = "git",
        [string]$Branch = "main"
    )
    $ref = "refs/heads/$Branch"
    $originLine = & $Git ls-remote origin $ref 2>$null | Select-Object -First 1
    $giteeLine = & $Git ls-remote gitee $ref 2>$null | Select-Object -First 1
    if (-not $originLine) {
        throw "GitHub origin missing branch $Branch. Check network/proxy and retry push."
    }
    if (-not $giteeLine) {
        throw "Gitee remote missing branch $Branch. Check network/credentials and retry push."
    }
    $originSha = ($originLine -split '\s+', 2)[0]
    $giteeSha = ($giteeLine -split '\s+', 2)[0]
    if ($originSha -ne $giteeSha) {
        throw "origin and gitee $Branch differ (origin=$originSha gitee=$giteeSha). Align remotes before Release."
    }
    Write-Host "Remotes aligned on $Branch @ $($originSha.Substring(0, 7))" -ForegroundColor Green
}
