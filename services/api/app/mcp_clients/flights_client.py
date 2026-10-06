"""Typed wrapper for the flights MCP tool (mcp-flights-server, Duffel-backed).

NOTE (22 Aug 2026): @traceable is a no-op when LANGCHAIN_TRACING_V2
isn't set - see weather_client.py's NOTE for the full reasoning, same
here for all 5 mcp_clients/*.py wrappers."""
from __future__ import annotations

from langsmith import traceable

from app.core.config import settings
from app.mcp_clients.base import call_cached_tool


@traceable(name="flights", run_type="tool")
async def search_flights(origin: str, destination: str, date: str, passengers: int = 1) -> list[dict]:
    return await call_cached_tool(
        server_url=settings.MCP_FLIGHTS_SERVER_URL,
        tool_name="search_flights",
        arguments={"origin": origin, "destination": destination, "date": date, "passengers": passengers},
        ttl_seconds=settings.FLIGHTS_CACHE_TTL_SECONDS,
    )
