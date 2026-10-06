# =====================================================================
#  stop-everything.ps1
#  Shuts down the databases. Double-click stop-everything.bat to run.
# =====================================================================
$root = $PSScriptRoot

Write-Host "Stopping the databases (Postgres, Redis, Qdrant)..." -ForegroundColor Cyan
Push-Location "$root\infra"
docker compose down
Pop-Location

Write-Host "`nDatabases stopped." -ForegroundColor Green
Write-Host "Now close the other 7 windows that popped up earlier (the 5 tool workers," -ForegroundColor Cyan
Write-Host "the backend, and the website) - just click the X on each one," -ForegroundColor Cyan
Write-Host "or click inside each and press Ctrl+C." -ForegroundColor Cyan
Read-Host "`nPress Enter to close this window"
