# Friday desktop autostart (silent)
# Install:  powershell -ExecutionPolicy Bypass -File scripts\install-friday-autostart.ps1
# Remove:   powershell -ExecutionPolicy Bypass -File scripts\install-friday-autostart.ps1 -Remove
# Prefers dist/Friday/Friday.exe when present; falls back to dev pythonw + run.py.

param([switch]$Remove)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot "friday-dist.ps1")

$Flag = if ($Remove) { "False" } else { "True" }
$DistDir = Get-FridayDistDir -Root $Root
$PackagedExe = Get-FridayExe -DistDir $DistDir

$Python = Join-Path $Root ".python-env\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = Join-Path $Root ".venv\Scripts\python.exe"
}
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

if ($PackagedExe) {
    $ExeArg = $PackagedExe.FullName.Replace("'", "''")
    & $Python -c @"
import json, sys
sys.path.insert(0, r'$Root')
from friday.autostart import set_autostart_enabled
print(json.dumps(set_autostart_enabled($Flag, executable=r'$ExeArg'), ensure_ascii=False))
"@
} else {
    & $Python -c "import json, sys; sys.path.insert(0, r'$Root'); from friday.autostart import set_autostart_enabled; print(json.dumps(set_autostart_enabled($Flag), ensure_ascii=False))"
}
