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

NOTE (22 Aug 2026, found via a real user report - LangSmith traces
never showing up despite .env being correct, uvicorn restarted, a trip
planned): pydantic-settings' `env_file=".env"` below reads the .env file
ONLY into this Settings object's own declared fields - it does NOT put
those values into the process's actual os.environ. That's invisible for
every setting THIS file declares (GROQ_API_KEY, DATABASE_URL, etc. -
they're all read through `settings.X`, never os.environ directly), but
LANGCHAIN_TRACING_V2/LANGCHAIN_API_KEY/LANGCHAIN_PROJECT are read
directly from os.environ by the langsmith/langgraph SDKs themselves,
completely outside this Settings class - so they silently never took
effect no matter how correctly they were set in .env. Every
mcp-*-server/server.py already calls load_dotenv() for exactly this
reason (see their own headers); the API just never did. python-dotenv
is already a pinned dependency (requirements.txt) - this was a one-line
gap, not a missing library.
"""
from __future__ import annotations

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Must run before Settings() is constructed below AND before any other
# module reads an env var directly (LangSmith's tracing config does,
# the moment the first LLM/graph call happens) - this is the actual
# process environment, not just this file's own pydantic model.
load_dotenv()


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

    # Added 21 Aug 2026 - currency conversion for BudgetAgent (see its
    # 21 Aug 2026 NOTE and app/core/fx.py). Frankfurter is free, keyless,
    # and ECB-backed - same "free/keyless where possible" pattern as
    # Open-Meteo/Nominatim/Overpass elsewhere in this project. ECB
    # updates rates once a day on business days, so a long cache TTL
    # doesn't cost accuracy - it just avoids hammering a free public API.
    #
    # NOTE (21 Aug 2026, updated after a real deployment hit this):
    # Frankfurter's old domain (api.frankfurter.app) now 301-redirects
    # to api.frankfurter.dev/v1/... - pointing here directly skips that
    # dead hop. See app/core/fx.py's NOTE for the full story.
    FX_API_URL: str = "https://api.frankfurter.dev/v1/latest"
    FX_CACHE_TTL_SECONDS: int = 60 * 60 * 24  # 24h - ECB rates update once/day at most

    # Phase 5 - LLM. Used by IntentAgent (parse free-text request) and
    # SchedulingAgent (assemble the day-by-day itinerary). If the chosen
    # provider's key is missing/invalid, agents fall back to
    # heuristic/rule-based logic instead of crashing the whole planning
    # run - see app/agents/intent_agent.py.
    #
    # LLM_PROVIDER picks which client app/core/llm.py builds: "groq"
    # (default - free tier, OpenAI-compatible API, needs GROQ_API_KEY) or
    # "openai" (needs OPENAI_API_KEY - useful when a Groq model gets
    # deprecated/renamed out from under GROQ_MODEL, or when someone
    # already has OpenAI credits and would rather use those).
    LLM_PROVIDER: str = "groq"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Phase 5 - LangGraph's Postgres checkpointer uses psycopg (not
    # asyncpg, which the rest of this app uses via SQLAlchemy) - it needs
    # a plain "postgresql://" URL, not SQLAlchemy's "postgresql+asyncpg://"
    # driver-qualified form. Derived once here so nobody has to remember
    # to convert it by hand.
    @property
    def CHECKPOINTER_DATABASE_URL(self) -> str:
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    # Phase 6 - RAG (destination-guide retrieval). Local embedding/rerank
    # models, not a paid API - see app/rag/embeddings.py's docstring for
    # why. Dimensions must match BAAI/bge-small-en-v1.5's actual output
    # size (384) - if this model is ever swapped, this MUST be updated
    # too, or Qdrant's collection vector size and the embeddings it's
    # sent will silently mismatch.
    QDRANT_COLLECTION: str = "destination_guides"
    RAG_EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    RAG_EMBEDDING_DIMENSIONS: int = 384
    RAG_CHUNK_SIZE: int = 800
    RAG_TOP_K_RETRIEVAL: int = 8
    RAG_TOP_K_RERANK: int = 4
    # Dense vs BM25 weight in Reciprocal Rank Fusion - dense weighted
    # higher because destination-guide queries are usually a city name
    # plus loose preference words ("Goa - food, beaches"), which is
    # exactly the semantic-similarity case dense search is good at;
    # BM25 still matters for exact place names dense search might blur.
    RAG_DENSE_WEIGHT: float = 0.6
    RAG_BM25_WEIGHT: float = 0.4


settings = Settings()
