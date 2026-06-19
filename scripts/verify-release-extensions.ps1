# 对比源码 extensions/ 与打包产物 _internal/extensions/（P0-3 发版门禁）
param(
    [string]$DistExtensions = ""
)

$ErrorActionPreference = "Stop"
if (-not $PSScriptRoot) {
    throw "verify-release-extensions.ps1 must be invoked with -File"
}
$FridayRepo = (Get-Item -LiteralPath $PSScriptRoot).Parent.FullName
Set-Location -LiteralPath $FridayRepo

. (Join-Path $PSScriptRoot "friday-dist.ps1")

if (-not $DistExtensions) {
    $DistApp = Get-FridayDistDir -Root $FridayRepo
    $DistExtensions = Join-Path (Join-Path $DistApp "_internal") "extensions"
}

$SrcRoot = Join-Path $FridayRepo "extensions"
if (-not (Test-Path -LiteralPath $SrcRoot)) {
    throw "Source extensions missing: $SrcRoot"
}
if (-not (Test-Path -LiteralPath $DistExtensions)) {
    throw "Dist extensions missing: $DistExtensions (run build first)"
}

$requiredManifests = @(
    "vision-bridge\friday-plugin.json",
    "storage-analyzer\friday-plugin.json",
    "ppt-master\friday-plugin.json",
    "file-safety\friday-plugin.json",
    "karpathy-guidelines\friday-plugin.json"
)

$pptMarker = "ppt-master\scripts\svg_to_pptx.py"
$errors = @()

foreach ($rel in $requiredManifests) {
    $src = Join-Path $SrcRoot $rel
    $dst = Join-Path $DistExtensions $rel
    if (-not (Test-Path -LiteralPath $src)) {
        $errors += "source missing: extensions\$rel"
    }
    if (-not (Test-Path -LiteralPath $dst)) {
        $errors += "dist missing: $rel"
    }
}

$srcPpt = Join-Path $SrcRoot $pptMarker
$dstPpt = Join-Path $DistExtensions $pptMarker
if (Test-Path -LiteralPath $srcPpt) {
    if (-not (Test-Path -LiteralPath $dstPpt)) {
        $errors += "dist missing full ppt-master skill: $pptMarker (friday.spec must bundle all extensions/ppt-master/)"
    }
} else {
    Write-Host "WARN: source $pptMarker missing — run scripts\sync_ppt_master_skill.ps1 before release" -ForegroundColor Yellow
}

if ($errors.Count -gt 0) {
    Write-Host "Extensions verify FAILED:" -ForegroundColor Red
    $errors | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    exit 1
}

Write-Host "Extensions verify OK: $DistExtensions" -ForegroundColor Green
exit 0
