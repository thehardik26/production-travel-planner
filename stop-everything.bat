@echo off
REM Double-click ME when you're done, to shut down the databases.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-everything.ps1"
pause
