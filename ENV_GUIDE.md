# Wanderplan — Environment Configuration Guide

This guide explains every environment variable used in Wanderplan, where each file is located, how to obtain free API keys, and what happens if a key is omitted.

---

## Quick Reference Summary

| Location | Purpose | Key Required? |
| :--- | :--- | :--- |
| [`infra/.env`](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/infra/.env) | PostgreSQL, Redis, Qdrant container config | ❌ Default credentials work out of the box |
| [`services/api/.env`](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/services/api/.env) | Backend, Auth, DB connections, Groq LLM | ⚠️ `GROQ_API_KEY` (Free, fallback if missing) |
| [`services/mcp-flights-server/.env`](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/services/mcp-flights-server/.env) | Flight search service | ⚠️ `DUFFEL_API_KEY` (Free test token, optional) |
| [`services/mcp-hotels-server/.env`](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/services/mcp-hotels-server/.env) | Hotel lookup service | ⚠️ `GOOGLE_PLACES_API_KEY` (Optional) |
| [`services/mcp-weather-server/.env`](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/services/mcp-weather-server/.env) | Weather forecast service | ❌ No API key needed (Open-Meteo) |
| [`services/mcp-attractions-server/.env`](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/services/mcp-attractions-server/.env) | Attractions service | ❌ No API key needed (OpenStreetMap) |
| [`services/mcp-transport-server/.env`](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/services/mcp-transport-server/.env) | Local transit service | ❌ No API key needed (OpenStreetMap) |
| [`frontend/.env`](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/frontend/.env) | React UI configuration | ❌ Default points to `http://localhost:8000` |

---

## 1. Backend API (`services/api/.env`)

Located at: [services/api/.env](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/services/api/.env)

```env
APP_NAME=Production Travel Planner
ENV=development

# Database connections
DATABASE_URL=postgresql+asyncpg://travel_admin:travel_pass@localhost:5432/travel_planner
REDIS_URL=redis://localhost:6380/0
QDRANT_URL=http://localhost:6335

# Authentication & Security
JWT_SECRET_KEY=dev-only-secret-change-me
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# MCP Tool Servers Endpoints
MCP_WEATHER_SERVER_URL=http://localhost:8001/mcp
MCP_FLIGHTS_SERVER_URL=http://localhost:8002/mcp
MCP_HOTELS_SERVER_URL=http://localhost:8003/mcp
MCP_ATTRACTIONS_SERVER_URL=http://localhost:8004/mcp
MCP_TRANSPORT_SERVER_URL=http://localhost:8005/mcp

# Database Pool & Rate Limiting
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
RATE_LIMIT_PER_MINUTE=30

# LLM Configuration (Groq)
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
```

### Detailed Field Breakdown:
- **`DATABASE_URL`**: SQLAlchemy asyncpg connection string used for standard queries (`users`, `trips`).
- **`REDIS_URL`**: Used for two things:
  1. Distributed rate limiting (`slowapi`).
  2. Cache-aside storage for MCP tool call outputs.
- **`QDRANT_URL`**: Vector store endpoint for hybrid RAG search. If unavailable, falls back to BM25 sparse search.
- **`JWT_SECRET_KEY`**: Symmetric secret key used to sign and verify JWT authentication tokens.
- **`MCP_*_SERVER_URL`**: HTTP endpoints where the backend reaches each isolated tool server.
- **`GROQ_API_KEY`**:
  - **Where to get**: Free signup at [console.groq.com](https://console.groq.com).
  - **What happens if empty**: The backend uses fallback heuristic parsing for `IntentAgent` and a round-robin schedule generator for `SchedulingAgent`.

---

## 2. Infrastructure Containers (`infra/.env`)

Located at: [infra/.env](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/infra/.env)

```env
POSTGRES_USER=travel_admin
POSTGRES_PASSWORD=travel_pass
POSTGRES_DB=travel_planner

DATABASE_URL=postgresql+asyncpg://travel_admin:travel_pass@localhost:5432/travel_planner
REDIS_URL=redis://localhost:6380/0
QDRANT_URL=http://localhost:6335
```

- Configures credentials for the PostgreSQL container in `infra/docker-compose.yml`.
- Local development defaults work without modification.

---

## 3. Tool Servers (`services/mcp-*-server/.env`)

### Flights Server (`services/mcp-flights-server/.env`)
- **`DUFFEL_API_KEY`**:
  - **Where to get**: [app.duffel.com/join](https://app.duffel.com/join) (Dashboard → More → Developers → Access tokens → Create a **TEST** token starting with `duffel_test_`).
  - **What happens if empty**: Returns an honest empty list with an error message; the rest of the trip plan continues unaffected.

### Hotels Server (`services/mcp-hotels-server/.env`)
- **`GOOGLE_PLACES_API_KEY`**:
  - **Where to get**: Google Cloud Console → Enable "Places API (New)" → Create API Key.
  - **What happens if empty**: Returns empty lodging list; the itinerary is scheduled without specific hotel anchors.

### Weather, Attractions, and Transport Servers
- **`OSM_USER_AGENT`**: A descriptive user-agent string required by OpenStreetMap Nominatim/Overpass usage policies (e.g., `production-travel-planner/1.0 (contact@example.com)`).
- **No paid API keys are required.**

---

## 4. Frontend (`frontend/.env`)

Located at: [frontend/.env](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/frontend/.env)

```env
VITE_API_BASE_URL=http://localhost:8000
```

- Specifies the backend URL for API requests.
- Only variables prefixed with `VITE_` are bundled into client-side code by Vite.
