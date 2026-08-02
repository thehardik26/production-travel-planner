"""
Shared pytest fixtures for the API's test suite.

WHY THIS IS AN INTEGRATION SUITE, NOT UNIT TESTS WITH MOCKS: `app.state.graph`
(the LangGraph checkpointer) needs a real Postgres connection, and the
rate limiter (app/core/rate_limit.py) needs a real Redis connection - both
are opened at FastAPI startup via the `lifespan` context in app/main.py.
Mocking all of that out would test something other than the actual app.
Instead, this suite runs against your ACTUAL local dev stack: Postgres +
Redis (via `docker-compose up` in infra/) and the 5 MCP tool servers
(`python server.py` in each services/mcp-*-server/) all need to be
running before `pytest` is run here - same stack you've been manually
curling this whole session. That's deliberate: the whole point of this
smoke test is to catch the class of regression this session kept hitting
(a tool server not restarted, a bad URL, a broken date) with one command
instead of manual curls.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# NOTE (21 Jul 2026): must be set BEFORE `from app.main import app` below,
# since that import chain constructs `settings = Settings()` (reading
# env vars) and builds the SQLAlchemy engine in app/db/database.py at
# import time. settings.ENV == "test" switches that engine to NullPool -
# see the note in database.py for why (pooled asyncpg connections don't
# survive being reused across the different asyncio Tasks pytest-asyncio
# gives each fixture). setdefault so a real ENV already set in the shell
# isn't clobbered.
os.environ.setdefault("ENV", "test")

# NOTE (Windows only): asyncio's default event loop on Windows is
# ProactorEventLoop, but psycopg (v3, used by langgraph-checkpoint-postgres
# for the checkpointer connection opened in app/orchestration/graph.py)
# can't run in async mode on Proactor - it raises
# "psycopg.InterfaceError: Psycopg cannot use the 'ProactorEventLoop'".
# SelectorEventLoop is the one psycopg's async support actually works
# with. This must run at import time (module load), before
# pytest-asyncio creates its event loop for the first fixture - setting
# it inside a fixture would be too late. No-op on Linux/macOS, where the
# default loop is already selector-based and this attribute doesn't
# exist that way.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.main import app


@pytest_asyncio.fixture
async def client():
    """An httpx client wired directly to the FastAPI ASGI app (no real
    socket/port needed), with the app's lifespan (Postgres checkpointer +
    Redis-backed limiter setup) actually run - same startup path as
    `uvicorn app.main:app` uses in production."""
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    """Signs up a fresh, uniquely-emailed user and logs in, returning a
    ready-to-use Authorization header. Fresh per test run so re-running
    the suite never collides with a previous run's user (signup 409s on
    a duplicate email)."""
    email = f"smoketest-{uuid.uuid4().hex[:12]}@example.com"
    password = "smoke-test-password-123"

    signup_resp = await client.post("/api/auth/signup", json={"email": email, "password": password})
    assert signup_resp.status_code == 201, f"signup failed: {signup_resp.text}"

    login_resp = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200, f"login failed: {login_resp.text}"

    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
