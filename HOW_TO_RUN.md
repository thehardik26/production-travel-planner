# How to run this project (Windows)

Two scripts do everything: `start-everything.bat` and `stop-everything.bat`, sitting right in the project's root folder. This file explains the setup, ports, and troubleshooting.

For an in-depth understanding of the system, consult the following guides:
- [PROJECT_OVERVIEW.md](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/PROJECT_OVERVIEW.md) — Complete architecture and system design.
- [ENV_GUIDE.md](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/ENV_GUIDE.md) — Detailed breakdown of all `.env` files and API keys.
- [AGENTS_AND_WORKFLOW.md](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/AGENTS_AND_WORKFLOW.md) — Multi-agent LangGraph workflow.

---

## Prerequisites (install these once)

- **Python 3.11 or newer** — https://python.org/downloads
- **Node.js** — https://nodejs.org
- **Docker Desktop** — https://www.docker.com/products/docker-desktop (must be *open and running* — look for the whale icon — every time you start the project)

`start-everything.bat` checks for all three and tells you exactly what's missing if one isn't found.

---

## One-time setup (Configuration files)

The project needs `.env` configuration files across services:

| Copy this... | ...to this | Fill in |
|---|---|---|
| `infra/.env.example` | `infra/.env` | Nothing — defaults work for local dev |
| `services/api/.env.example` | `services/api/.env` | `GROQ_API_KEY` — free at https://console.groq.com |
| `services/mcp-flights-server/.env.example` | `services/mcp-flights-server/.env` | `DUFFEL_API_KEY` — free test token at https://app.duffel.com/join |
| `services/mcp-hotels-server/.env.example` | `services/mcp-hotels-server/.env` | `GOOGLE_PLACES_API_KEY` — Google Cloud Places API (New) |
| `services/mcp-weather-server/.env.example` | `services/mcp-weather-server/.env` | Nothing — Open-Meteo needs no key |
| `services/mcp-attractions-server/.env.example` | `services/mcp-attractions-server/.env` | Nothing |
| `services/mcp-transport-server/.env.example` | `services/mcp-transport-server/.env` | Nothing |
| `frontend/.env.example` | `frontend/.env` | Nothing — default points to local backend |

> **Graceful Degradation Note:** Without `GROQ_API_KEY`, the app still runs — `IntentAgent` and `SchedulingAgent` fall back to rule-based heuristic modes. Missing flight/hotel keys simply omit those specific search results while planning the rest of the trip.

---

## Starting the project

Double-click **`start-everything.bat`**. It runs `start-everything.ps1` and boots the system in four phases:

1. **Databases (Docker)** — Brings up Postgres (`:5432`), Redis (`:6380`), and Qdrant (`:6335`).
2. **Tool Workers (MCP)** — Starts weather (`:8001`), flights (`:8002`), hotels (`:8003`), attractions (`:8004`), and transport (`:8005`).
3. **Backend API** — Runs database migrations via Alembic, then starts FastAPI on port `8000` via `services/api/run.py` (which configures the Windows event loop policy).
4. **Frontend UI** — Starts Vite on port `5173` and automatically opens `http://localhost:5173` in your browser.

You will have terminal windows open for the running services. Leave them open while using the application.

---

## Port Map Reference

| Service | Port | Status URL / Endpoint |
|---|---|---|
| Frontend (React) | `5173` | http://localhost:5173 |
| Backend API (FastAPI) | `8000` | http://localhost:8000/docs |
| Weather Worker | `8001` | http://localhost:8001/mcp |
| Flights Worker | `8002` | http://localhost:8002/mcp |
| Hotels Worker | `8003` | http://localhost:8003/mcp |
| Attractions Worker | `8004` | http://localhost:8004/mcp |
| Transport Worker | `8005` | http://localhost:8005/mcp |
| PostgreSQL | `5432` | `localhost:5432` |
| Redis Cache | `6380` | `localhost:6380` |
| Qdrant Vector DB | `6335` | `localhost:6335` |

---

## Stopping the project

Double-click **`stop-everything.bat`**. It stops the Docker containers (Postgres/Redis/Qdrant). Then close the remaining terminal windows (or press `Ctrl+C`).

---

## Troubleshooting

- **"Docker doesn't seem to be running"**: Launch Docker Desktop first, wait for the engine to report "Running", then re-run `start-everything.bat`.
- **Backend fails on Windows with `ProactorEventLoop`**: The backend uses [services/api/run.py](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/services/api/run.py) which sets `asyncio.WindowsSelectorEventLoopPolicy()` for `psycopg` compatibility. Run using `python run.py` inside `services/api/.venv`.
- **API key errors**: Inspect the terminal output for port 8000 or the specific tool server on ports 8001-8005. Refer to [ENV_GUIDE.md](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/ENV_GUIDE.md).
