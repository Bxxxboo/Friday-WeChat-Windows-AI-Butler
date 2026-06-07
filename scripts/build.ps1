$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$python = Join-Path $PWD ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "venv not found, run setup.ps1 first" -ForegroundColor Yellow
    exit 1
}

Write-Host "Installing dependencies..."
& $python -m pip install pyinstaller cryptography --quiet

Write-Host "Creating icon..."
& $python scripts/create_icon.py

Write-Host "Building exe (1-3 min)..."
& $python -m PyInstaller friday.spec --noconfirm --clean

$AppFolder = -join ([char]0x661F, [char]0x671F, [char]0x4E94)
$exe = Get-ChildItem (Join-Path $PWD (Join-Path "dist" $AppFolder)) -Filter "*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $exe) {
    $exe = Get-ChildItem (Join-Path $PWD "dist") -Filter "*.exe" | Select-Object -First 1
}
if ($exe) {
    Copy-Item -Path (Join-Path $PWD "assets\friday.ico") -Destination (Join-Path $exe.DirectoryName "app.ico") -Force
    Write-Host "Done: $($exe.FullName)" -ForegroundColor Green
} else {
    Write-Host "Build failed, see errors above." -ForegroundColor Red
    exit 1
}
