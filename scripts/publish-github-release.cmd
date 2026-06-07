@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish-github-release.ps1" %*
