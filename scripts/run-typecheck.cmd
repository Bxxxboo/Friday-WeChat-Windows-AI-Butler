@echo off
setlocal
cd /d "%~dp0.."
python -m pip install -q mypy>=1.11.0
python -m mypy friday/server.py friday/bundled.py friday/health_check.py friday/boot_timing.py friday/storage.py friday/safety.py friday/credentials_store.py friday/api/settings_helpers.py
exit /b %ERRORLEVEL%
