@echo off
REM Double-click ME to start the whole project.
REM This just tells Windows to run the real script (start-everything.ps1)
REM with permission to actually execute it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-everything.ps1"
pause
