"""
Async SQLAlchemy engine/session, pointed at the real Postgres container
from Phase 1 (via app.core.config.settings.DATABASE_URL).

Table creation is NOT done here (no create_all() call) - from this phase
onward, Alembic migrations own the schema, so every change is tracked and
versioned instead of silently applied whenever the app happens to start.

Phase 4 - connection pool sized explicitly (not left to the driver
default) because this is the actual answer to "what happens when 50
users hit the API at the same second": each request borrows one
connection from this pool for the duration of its DB work and returns
it when done. pool_size is how many stay open and warm; max_overflow is
how many extra get created under a burst before new requests start
queueing instead of erroring. Too small -> requests queue/timeout under
load; too large -> Postgres itself falls over (it has its own
max_connections limit, shared across every API replica connecting to
it) - so this number has to be chosen with that ceiling in mind, not
just increased blindly.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

# NOTE (21 Jul 2026, settings.ENV == "test" only): pytest-asyncio gives
# EACH async fixture (and the test function itself) its OWN asyncio
# Task, even when they all share one event loop (see tests/conftest.py's
# session-loop-scope note). A pooled asyncpg connection checked out
# during one fixture's Task (e.g. auth_headers doing signup/login) and
# reused later from a DIFFERENT Task (the test body's own request) makes
# asyncpg raise "attached to a different loop" - the connection's
# internal protocol Future is tied to whichever Task first drove it.
# NullPool sidesteps this entirely: every checkout opens a brand new
# physical connection and closes it on checkin instead of reusing one,
# so a connection is never handed from one Task to another. Production
# (ENV=development/production) keeps the real sized pool from
# DB_POOL_SIZE/DB_MAX_OVERFLOW - this only applies under pytest.
_use_null_pool = settings.ENV == "test" or settings.DATABASE_URL.startswith("sqlite")

_pool_kwargs = (
    {"poolclass": NullPool}
    if _use_null_pool
    else {"pool_size": settings.DB_POOL_SIZE, "max_overflow": settings.DB_MAX_OVERFLOW}
)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=not _use_null_pool,  # detect a dropped/stale pooled connection before using it - moot with NullPool, which never reuses one
    **_pool_kwargs,
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
