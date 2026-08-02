"""
The trip-planning graph: intent -> budget_gate -> research -> budget ->
scheduling -> verification, mostly a straight line except for ONE
conditional edge: budget_gate can short-circuit straight to END if the
stated budget is unrealistic (see agents/budget_gate_agent.py) - that's
deliberately BEFORE research (5 real network calls) and scheduling (a
second LLM call), so an unwinnable request doesn't pay for either.

`build_graph()` wires the agents onto a LangGraph StateGraph, given an
already-open checkpointer. `production_graph()` is the context manager
app/main.py's FastAPI lifespan uses: it opens ONE Postgres connection
pool for the whole app's lifetime (not one per request - that would be
its own multi-user/connection-exhaustion problem, same reasoning as the
SQLAlchemy pool in app/db/database.py), runs the checkpointer's
one-time table setup, and yields the compiled graph.

IMPORTANT: the checkpointer's tables are NOT managed by our Alembic
migrations (app/db/models.py / alembic/versions/). langgraph-checkpoint-
postgres owns its own schema via `checkpointer.setup()`, which is
idempotent (safe to call on every app startup - it only creates tables
if they don't already exist). Two separate migration mechanisms, for
two separate concerns: our own `users`/`trips` tables vs. LangGraph's
internal state-persistence tables.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

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


@asynccontextmanager
async def production_graph():
    """One Postgres-backed checkpointer + compiled graph for the app's
    entire lifetime - opened in app/main.py's lifespan, not per-request."""
    async with AsyncPostgresSaver.from_conn_string(settings.CHECKPOINTER_DATABASE_URL) as checkpointer:
        await checkpointer.setup()
        yield build_graph(checkpointer)
