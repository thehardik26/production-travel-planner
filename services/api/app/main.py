"""
FastAPI app entrypoint.

Phase 3 wired up auth. Phase 4 added the tools router + Redis-backed
rate limiting. Phase 5 adds the real product endpoint (trips router,
POST /api/trips/plan) and a startup lifespan that opens LangGraph's
Postgres checkpointer connection pool ONCE for the app's lifetime -
same pooling principle as app/db/database.py's SQLAlchemy engine, just
for the orchestration layer's state persistence instead of our own
users/trips tables.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import auth as auth_routes
from app.api.routes import tools as tools_routes
from app.api.routes import trips as trips_routes
from app.core.config import settings
from app.core.rate_limit import limiter
from app.orchestration.graph import production_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with production_graph() as graph:
        app.state.graph = graph
        yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# NOTE (21 Jul 2026): SlowAPIMiddleware deliberately NOT added.
# It subclasses Starlette's BaseHTTPMiddleware, which runs each request
# in its OWN spawned anyio Task (a documented Starlette quirk - see
# starlette/middleware/base.py's `async with anyio.create_task_group()`).
# Combined with SQLAlchemy's async engine (pool_pre_ping=True in
# app/db/database.py, which pings a pooled connection before reusing
# it), a connection first used in one request's Task and pinged again
# while being checked out for a DIFFERENT request's Task made asyncpg
# raise "RuntimeError: ... got Future ... attached to a different loop"
# - reproduced reliably by tests/test_trip_plan_smoke.py's multi-request
# flow (signup -> login -> plan -> list -> get, all reusing the pool).
# Every route already has its own @limiter.limit(...) decorator (see
# app/api/routes/*.py) - that decorator is what actually performs the
# rate-limit check and raises RateLimitExceeded (caught by the handler
# above); SlowAPIMiddleware only adds informational X-RateLimit-* response
# headers on top of that. Losing those headers is an acceptable trade
# for not having the app's own request-handling architecture fight its
# own database driver.


# NOTE (19 Jul 2026): added alongside the React frontend (Phase 10-ish -
# not in the original 9-phase blueprint, added once the backend was
# actually working end to end). The frontend dev server (Vite,
# localhost:5173) and this API (localhost:8000) are different origins,
# so without CORS the browser blocks every fetch() before it even
# leaves - not a backend bug, just how browsers enforce same-origin by
# default. allow_credentials=True + explicit origins (not "*") because
# credentials mode disallows a wildcard origin anyway.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(tools_routes.router)
app.include_router(trips_routes.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": settings.ENV}
