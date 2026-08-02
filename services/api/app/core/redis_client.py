"""
Shared async Redis connection pool for the whole API process.

Why a pool instead of one connection: every concurrent request that
needs Redis (cache reads in mcp_clients/, rate-limit counters) borrows a
connection from this pool and gives it back when done, the same idea as
the Postgres pool in app/db/database.py. One global `redis_client` is
safe to import and reuse everywhere - redis-py's pool is what makes it
safe to share across concurrent async requests, so nobody has to import
this file and immediately think about locking.

`get_redis()` (rather than importing `redis_client` directly everywhere)
exists so tests can swap in fakeredis via FastAPI's dependency-override
mechanism instead of needing a real Redis server.
"""
from __future__ import annotations

import redis.asyncio as redis

from app.core.config import settings

redis_client: redis.Redis = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=50,
)


async def get_redis() -> redis.Redis:
    return redis_client
