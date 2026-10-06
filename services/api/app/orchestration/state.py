"""
Shared state schema for the trip-planning graph. Every agent node
receives this (or a subset via LangGraph's partial-update merging) and
returns a partial dict of the fields it changed - LangGraph merges that
into the running state and checkpoints it to Postgres after every node.

Why a single shared TypedDict instead of each agent inventing its own
shape: this IS the contract between agents. IntentAgent doesn't need to
know how ResearchAgent uses `destination` - it just needs to agree on
the field name. Same principle as MCP tool schemas in Phase 4: a shared,
explicit shape instead of implicit coupling between components.
"""
from __future__ import annotations

from typing import Any, TypedDict


class TripPlanningState(TypedDict, total=False):
    # input
    user_query: str
    user_id: str

    # filled by IntentAgent
    origin: str | None
    destination: str | None
    start_date: str | None  # YYYY-MM-DD
    end_date: str | None
    travelers: int
    budget: float | None
    budget_currency: str
    preferences: list[str]  # e.g. ["food", "culture"]

    # filled by BudgetGateAgent - True means the request was rejected
    # before any tool calls or the SchedulingAgent's LLM call ran (see
    # orchestration/graph.py's conditional edge out of "budget_gate")
    budget_rejected: bool

    # filled by ResearchAgent - raw tool results, one key per MCP tool
    weather: dict | None
    flights: list[dict]
    hotels: list[dict]
    attractions: list[dict]
    transport: list[dict]

    # filled by ResearchAgent - Phase 6 RAG lookup, not an MCP tool but
    # gathered the same way (concurrently, independently failable) -
    # see app/rag/destination_guide.py. None means "no guide content
    # found or RAG unavailable", same convention as `weather`.
    destination_guide: dict | None

    # filled by BudgetAgent
    budget_summary: dict | None

    # filled by SchedulingAgent
    itinerary: dict | None

    # filled by VerificationAgent
    warnings: list[str]

    # accumulated by any agent that hits a recoverable problem (a tool
    # failed, the LLM fell back to heuristics, etc.) - surfaced to the
    # caller instead of silently disappearing
    errors: list[str]
