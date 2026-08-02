"""
Centralized application settings.

Why this file exists: every later phase (DB, auth, MCP clients, RAG,
observability) needs configuration values - database URLs, secrets, API
keys. Instead of each module calling os.getenv() directly, which scatters
config across the codebase and fails silently on a typo'd variable name,
every setting is declared once here with an explicit type. Pydantic
validates all of them at startup, so a malformed value crashes immediately
with a clear error message instead of failing mysteriously deep inside a
request handler hours later.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Production Travel Planner"
    ENV: str = "development"

    # Frontend origins allowed to call this API cross-origin (see the
    # CORSMiddleware note in main.py). Vite's default dev port is 5173;
    # 3000 covers Create-React-App-style setups too, in case that's ever
    # swapped in instead.
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]

    # Phase 1 - infra endpoints, matching infra/docker-compose.yml
    DATABASE_URL: str = "postgresql+asyncpg://travel_admin:travel_pass@localhost:5432/travel_planner"
    REDIS_URL: str = "redis://localhost:6380/0"
    QDRANT_URL: str = "http://localhost:6335"

    # Phase 3 - auth. JWT_SECRET_KEY MUST be overridden via .env in any
    # real deployment - this default is only safe for local dev because
    # it's public in this file.
    JWT_SECRET_KEY: str = "dev-only-secret-change-me-in-.env"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24

    # Phase 4 - MCP tool servers (HTTP, one URL per independently
    # deployed service - see services/mcp-*-server/). Each has its own
    # cache TTL, chosen by how fast the underlying data actually changes
    # - flight/hotel prices move within minutes, forecasts within hours,
    # attraction/transport infrastructure barely ever.
    MCP_WEATHER_SERVER_URL: str = "http://localhost:8001/mcp"
    WEATHER_CACHE_TTL_SECONDS: int = 60 * 30  # 30 min - forecasts don't change fast

    MCP_FLIGHTS_SERVER_URL: str = "http://localhost:8002/mcp"
    FLIGHTS_CACHE_TTL_SECONDS: int = 60 * 10  # 10 min - prices move fast, don't cache stale quotes long

    MCP_HOTELS_SERVER_URL: str = "http://localhost:8003/mcp"
    HOTELS_CACHE_TTL_SECONDS: int = 60 * 15  # 15 min - same reasoning as flights

    MCP_ATTRACTIONS_SERVER_URL: str = "http://localhost:8004/mcp"
    ATTRACTIONS_CACHE_TTL_SECONDS: int = 60 * 60 * 24  # 24h - OSM POI data barely changes

    MCP_TRANSPORT_SERVER_URL: str = "http://localhost:8005/mcp"
    TRANSPORT_CACHE_TTL_SECONDS: int = 60 * 60 * 24  # 24h - same reasoning as attractions

    # Phase 4 - multi-user concurrency knobs. Explicit instead of
    # relying on library defaults, because "what happens under 100
    # concurrent users" needs an actual answer, not an assumption.
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    RATE_LIMIT_PER_MINUTE: int = 30

    # Phase 5 - LLM (Groq: free tier, OpenAI-compatible API). Used by
    # IntentAgent (parse free-text request) and SchedulingAgent (assemble
    # the day-by-day itinerary). If this key is missing/invalid, agents
    # fall back to heuristic/rule-based logic instead of crashing the
    # whole planning run - see app/agents/intent_agent.py.
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Phase 5 - LangGraph's Postgres checkpointer uses psycopg (not
    # asyncpg, which the rest of this app uses via SQLAlchemy) - it needs
    # a plain "postgresql://" URL, not SQLAlchemy's "postgresql+asyncpg://"
    # driver-qualified form. Derived once here so nobody has to remember
    # to convert it by hand.
    @property
    def CHECKPOINTER_DATABASE_URL(self) -> str:
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


settings = Settings()
