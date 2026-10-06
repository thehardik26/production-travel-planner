# =====================================================================
#  start-everything.ps1
#
#  Wakes up every piece of Wanderplan in the right order:
#    1. The three "storage rooms" (Postgres, Redis, Qdrant) via Docker
#    2. The five little "tool worker" servers (weather, flights, etc.)
#    3. The main backend brain (the API)
#    4. The website you actually look at (the frontend)
#  ...then opens it in your browser.
#
#  Just double-click start-everything.bat (next to this file) - you
#  don't need to run this .ps1 file directly.
# =====================================================================

$ErrorActionPreference = "Continue"
$root = $PSScriptRoot

function Write-Step($text) {
    Write-Host "`n=== $text ===" -ForegroundColor Cyan
}

function Test-CommandExists($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

function Wait-ForPort($hostName, $port, $label, $timeoutSeconds = 90) {
    Write-Host "  Waiting for $label to be ready..." -NoNewline
    $waited = 0
    while ($waited -lt $timeoutSeconds) {
        $ok = Test-NetConnection -ComputerName $hostName -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue
        if ($ok) {
            Write-Host " ready!" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 2
        $waited += 2
        Write-Host "." -NoNewline
    }
    Write-Host " still not responding after $timeoutSeconds seconds - continuing anyway." -ForegroundColor Yellow
    return $false
}

Write-Host "###########################################" -ForegroundColor Magenta
Write-Host "#     Starting Wanderplan - hang tight!    #" -ForegroundColor Magenta
Write-Host "###########################################" -ForegroundColor Magenta

# ---- Sanity checks -----------------------------------------------------
if (-not (Test-CommandExists "python")) {
    Write-Host "`nI can't find 'python' on your computer." -ForegroundColor Red
    Write-Host "Please install Python (3.11 or newer) from https://python.org/downloads then re-run this." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
if (-not (Test-CommandExists "npm")) {
    Write-Host "`nI can't find 'npm' (Node.js) on your computer." -ForegroundColor Red
    Write-Host "Please install Node.js from https://nodejs.org then re-run this." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
if (-not (Test-CommandExists "docker")) {
    Write-Host "`nI can't find 'docker' on your computer." -ForegroundColor Red
    Write-Host "Please install Docker Desktop from https://www.docker.com/products/docker-desktop then re-run this." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

# ---- 1. Storage rooms: Postgres, Redis, Qdrant (Docker) ----------------
Write-Step "Step 1 of 4: Waking up the databases (Docker)"
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker Desktop doesn't seem to be running." -ForegroundColor Red
    Write-Host "Please open Docker Desktop (the whale icon), wait until it says 'running', then re-run this script." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
Push-Location "$root\infra"
docker compose up -d
Pop-Location
Wait-ForPort "localhost" 5432 "the main database (Postgres)" | Out-Null
Wait-ForPort "localhost" 6380 "the fast-cache (Redis)" | Out-Null

# ---- 2. The five little tool workers ------------------------------------
Write-Step "Step 2 of 4: Waking up the tool workers (weather, flights, hotels, attractions, transport)"

function Start-ToolServer($name, $folderName, $port) {
    $path = "$root\services\$folderName"
    $venvPath = "$path\.venv"
    Write-Host "`n  -> $name (port $port)"
    if (-not (Test-Path $venvPath)) {
        Write-Host "     First time here - creating its own private toolbox (this takes a moment)..."
        python -m venv $venvPath
    }
    $pipExe = "$venvPath\Scripts\pip.exe"
    $pyExe = "$venvPath\Scripts\python.exe"
    Write-Host "     Making sure it has everything it needs..."
    & $pipExe install -q -r "$path\requirements.txt"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$path'; & '$pyExe' server.py" | Out-Null
    Write-Host "     Started in its own window." -ForegroundColor Green
}

Start-ToolServer "Weather worker"     "mcp-weather-server"     8001
Start-ToolServer "Flights worker"     "mcp-flights-server"     8002
Start-ToolServer "Hotels worker"      "mcp-hotels-server"      8003
Start-ToolServer "Attractions worker" "mcp-attractions-server" 8004
Start-ToolServer "Transport worker"   "mcp-transport-server"   8005

Start-Sleep -Seconds 3

# ---- 3. The main backend brain (API) ------------------------------------
Write-Step "Step 3 of 4: Waking up the main backend (the brain)"
$apiPath = "$root\services\api"
$apiVenv = "$apiPath\.venv"
if (-not (Test-Path $apiVenv)) {
    Write-Host "  First time here - creating its own private toolbox (this can take a couple of minutes)..."
    python -m venv $apiVenv
}
$apiPip = "$apiVenv\Scripts\pip.exe"
$apiPy = "$apiVenv\Scripts\python.exe"
Write-Host "  Making sure it has everything it needs..."
& $apiPip install -q -r "$apiPath\requirements.txt"

Write-Host "  Setting up its notebook (database tables)..."
Push-Location $apiPath
& $apiPy -m alembic upgrade head
Pop-Location

Write-Host "  Starting the brain in its own window (port 8000)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$apiPath'; & '$apiPy' run.py" | Out-Null

Wait-ForPort "localhost" 8000 "the backend" | Out-Null

# ---- 4. The website (frontend) -------------------------------------------
Write-Step "Step 4 of 4: Starting the website"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev" | Out-Null

Wait-ForPort "localhost" 5173 "the website" | Out-Null
Start-Sleep -Seconds 2

Write-Host "`n#################################################" -ForegroundColor Green
Write-Host "#  Everything is running! Opening your browser  #" -ForegroundColor Green
Write-Host "#################################################" -ForegroundColor Green
Start-Process "http://localhost:5173"

Write-Host "`nYou should now see 8 little windows total (this one plus 7 more) - that's totally normal!" -ForegroundColor Cyan
Write-Host "Each one is a piece of your app quietly working. Leave them ALL open while you use the site." -ForegroundColor Cyan
Write-Host "When you're done, just run stop-everything.bat (or close all the windows)." -ForegroundColor Cyan
Read-Host "`nPress Enter to close THIS window (the others will keep running)"
