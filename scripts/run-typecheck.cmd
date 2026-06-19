@echo off
setlocal
cd /d "%~dp0.."
python -m pip install -q mypy>=1.11.0
python -m mypy friday/server.py friday/bundled.py friday/health_check.py
exit /b %ERRORLEVEL%
