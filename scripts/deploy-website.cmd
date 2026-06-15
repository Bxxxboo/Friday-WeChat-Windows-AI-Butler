@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy-website.ps1" %*
