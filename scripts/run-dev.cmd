@echo off
rem 调试入口：会闪黑框。日常使用请双击桌面「星期五」或 run-dev.vbs
if /I not "%~1"=="__hidden__" (
  start "" /min mshta "javascript:try{new ActiveXObject('WScript.Shell').Run('\"\"\"%~f0\"\"\" __hidden__',0,false);close()}catch(e){close()}"
  exit /b
)
wscript.exe //B //Nologo "%~dp0run-dev.vbs"
