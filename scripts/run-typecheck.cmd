@echo off
setlocal
cd /d "%~dp0.."
python -m pip install -q mypy>=1.11.0
python -m mypy friday
exit /b %ERRORLEVEL%
