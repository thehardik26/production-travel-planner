"""
The trip-planning graph: intent -> budget_gate -> research -> budget ->
scheduling -> verification, mostly a straight line except for ONE
conditional edge: budget_gate can short-circuit straight to END if the
stated budget is unrealistic (see agents/budget_gate_agent.py) - that's
deliberately BEFORE research (5 real network calls) and scheduling (a
second LLM call), so an unwinnable request doesn't pay for either.

`build_graph()` wires the agents onto a LangGraph StateGraph, given an
already-open checkpointer. `production_graph()` is the context manager
app/main.py's FastAPI lifespan uses: it opens ONE Postgres connection for
the whole app's lifetime (not one per request - that would be its own
multi-user/connection-exhaustion problem, same reasoning as the
SQLAlchemy pool in app/db/database.py), runs the checkpointer's one-time
table setup, and yields the compiled graph.

IMPORTANT: the checkpointer's tables are NOT managed by our Alembic
migrations (app/db/models.py / alembic/versions/). langgraph-checkpoint-
postgres owns its own schema via `checkpointer.setup()`, which is
idempotent (safe to call on every app startup - it only creates tables
if they don't already exist). Two separate migration mechanisms, for
two separate concerns: our own `users`/`trips` tables vs. LangGraph's
internal state-persistence tables.

NOTE (21 Aug 2026): found via a real failure on a long-running dev
machine - that ONE checkpointer connection has no health check and no
automatic reconnect. If it goes stale for ANY reason (the machine sleeps
and the OS silently drops the idle TCP socket, the Postgres/Docker
container restarts, a brief network blip), every trip-planning request
fails with a raw "consuming input failed: server closed the connection
unexpectedly" error - the checkpointer has no way to know the connection
died until it tries to use it.

A first attempt at fixing this swapped the single connection for
psycopg_pool.AsyncConnectionPool (the direct equivalent of
app/db/database.py's `pool_pre_ping=True`, and AsyncPostgresSaver
natively accepts a pool in place of one connection). That's the
"textbook" fix, but it broke this project's own test suite: tests/
conftest.py runs the FULL app lifespan fresh for every single test
function, all sharing ONE session-scoped event loop (see conftest.py's
own note on why SQLAlchemy needs NullPool here) - opening and closing a
connection POOL's background maintenance tasks that many times against
one shared loop reliably hung by the 3rd/4th test. Same underlying
"pooled async connections don't always survive being juggled across
tasks/loops" class of problem this codebase already worked around once
for SQLAlchemy - a pool was one juggle too many for the checkpointer.

The actual fix here is smaller: keep the ONE-connection design exactly
as before (cheap, and known to work cleanly with the test suite's
per-test lifespan), but make it possible to detect a dead connection and
transparently open a fresh one - see `rebuild_after_dead_connection()`,
called from app/api/routes/trips.py when `graph.ainvoke()` fails with
that specific "connection is dead" signature. The very next request
after a stale connection self-heals instead of every request failing
until someone notices and restarts the whole API process.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from psycopg import AsyncConnection
from psycopg.rows import dict_row

from app.agents.budget_agent import BudgetAgent
from app.agents.budget_gate_agent import BudgetGateAgent
from app.agents.intent_agent import IntentAgent
from app.agents.research_agent import ResearchAgent
from app.agents.scheduling_agent import SchedulingAgent
from app.agents.verification_agent import VerificationAgent
from app.core.config import settings
from app.orchestration.state import TripPlanningState


def _route_after_budget_gate(state: TripPlanningState) -> str:
    """The one conditional branch in this graph. `budget_rejected` is
    set by BudgetGateAgent - True means the stated budget is provably
    unrealistic, so we skip straight to END instead of running research
    or scheduling for a request that could never succeed."""
    return "reject" if state.get("budget_rejected") else "continue"


def build_graph(checkpointer: BaseCheckpointSaver | None) -> CompiledStateGraph:
    graph = StateGraph(TripPlanningState)

    graph.add_node("intent", IntentAgent().run)
    graph.add_node("budget_gate", BudgetGateAgent().run)
    graph.add_node("research", ResearchAgent().run)
    graph.add_node("budget", BudgetAgent().run)
    graph.add_node("scheduling", SchedulingAgent().run)
    graph.add_node("verification", VerificationAgent().run)

    graph.add_edge(START, "intent")
    graph.add_edge("intent", "budget_gate")
    graph.add_conditional_edges(
        "budget_gate",
        _route_after_budget_gate,
        {"continue": "research", "reject": END},
    )
    graph.add_edge("research", "budget")
    graph.add_edge("budget", "scheduling")
    graph.add_edge("scheduling", "verification")
    graph.add_edge("verification", END)

    return graph.compile(checkpointer=checkpointer)


async def _open_checkpointer() -> AsyncPostgresSaver:
    """Open exactly one fresh raw psycopg connection, wrap it as a
    checkpointer, and run its (idempotent) table setup. The "cold start"
    path - used both at app startup and to recover after a dead
    connection is detected (see rebuild_after_dead_connection below)."""
    conn = await AsyncConnection.connect(
        settings.CHECKPOINTER_DATABASE_URL, autocommit=True, prepare_threshold=0, row_factory=dict_row
    )
    checkpointer = AsyncPostgresSaver(conn=conn)
    await checkpointer.setup()
    return checkpointer


async def rebuild_after_dead_connection(app_state) -> CompiledStateGraph:
    """Replace app.state.checkpointer/graph with a freshly-connected
    pair - called from trips.py's plan_trip() when a request discovers
    the checkpointer's long-lived connection has died. Best-effort close
    of the old (broken) connection first; if that also errors, that's
    expected (it's dead - that's exactly why we're here) and is not
    worth failing this recovery over."""
    old_checkpointer = getattr(app_state, "checkpointer", None)
    if old_checkpointer is not None:
        try:
            await old_checkpointer.conn.close()
        except Exception:
            pass

    new_checkpointer = await _open_checkpointer()
    new_graph = build_graph(new_checkpointer)
    app_state.checkpointer = new_checkpointer
    app_state.graph = new_graph
    return new_graph


@asynccontextmanager
async def production_graph():
    """One Postgres-backed checkpointer + compiled graph for the app's
    entire lifetime - opened in app/main.py's lifespan, not per-request."""
    checkpointer = await _open_checkpointer()
    try:
        yield checkpointer, build_graph(checkpointer)
    finally:
        await checkpointer.conn.close()
