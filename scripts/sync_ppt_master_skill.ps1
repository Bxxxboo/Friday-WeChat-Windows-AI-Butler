# 将 hugohe3/ppt-master@v2.9.0 的 skill 同步到 extensions/ppt-master/（发版前执行）
# 保留本仓库的 friday-plugin.json（星期五内置 manifest）
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Dest = Join-Path $Root "extensions\ppt-master"
$Tmp = Join-Path $Root ".tmp-ppt-master-sync"
$Tag = "v2.9.0"

if (Test-Path $Tmp) { Remove-Item -Recurse -Force $Tmp }
git clone --depth 1 --branch $Tag --filter=blob:none --sparse `
    "https://github.com/hugohe3/ppt-master.git" $Tmp
Set-Location $Tmp
git sparse-checkout set skills/ppt-master
Set-Location $Root

$Manifest = Join-Path $Dest "friday-plugin.json"
$ManifestBackup = $null
if (Test-Path $Manifest) {
    $ManifestBackup = Get-Content $Manifest -Raw
}
if (Test-Path $Dest) {
    Get-ChildItem $Dest -Force | Remove-Item -Recurse -Force
}
New-Item -ItemType Directory -Path $Dest -Force | Out-Null
Copy-Item -Recurse -Force (Join-Path $Tmp "skills\ppt-master\*") $Dest
if ($ManifestBackup) {
    Set-Content -Path $Manifest -Value $ManifestBackup -Encoding UTF8
}
Remove-Item -Recurse -Force $Tmp
Write-Host "已同步 ppt-master skill 到 $Dest（保留 friday-plugin.json）"
