"""
Typed wrapper for the weather MCP tool. Route handlers / agents call
`get_weather(city, date)` and never see the cache key, the HTTP
transport, or the MCP session handshake underneath - same principle as
the demo projects: callers depend on a tool's name and shape, not on
how it's fetched.

NOTE (22 Aug 2026): @traceable below is purely additive - if
LANGCHAIN_TRACING_V2 isn't set (see app/core/config.py's NOTE), it's a
harmless no-op wrapper. When tracing IS on, it makes this call show up
as its own named child span inside ResearchAgent's "research" node in
LangSmith, instead of the 5 concurrent lookups being one opaque block -
added after a real user asked "which one is actually slow?" while
looking at a trace where research took 21.72s of 38.06s total.
"""
from __future__ import annotations

from langsmith import traceable

from app.core.config import settings
from app.mcp_clients.base import call_cached_tool


@traceable(name="weather", run_type="tool")
async def get_weather(city: str, date: str) -> dict:
    return await call_cached_tool(
        server_url=settings.MCP_WEATHER_SERVER_URL,
        tool_name="get_weather",
        arguments={"city": city, "date": date},
        ttl_seconds=settings.WEATHER_CACHE_TTL_SECONDS,
    )
