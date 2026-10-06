"""Typed wrapper for the attractions MCP tool (mcp-attractions-server, OSM-backed).

NOTE (22 Aug 2026): @traceable is a no-op when LANGCHAIN_TRACING_V2
isn't set - see weather_client.py's NOTE for the full reasoning, same
here for all 5 mcp_clients/*.py wrappers."""
from __future__ import annotations

from langsmith import traceable

from app.core.config import settings
from app.mcp_clients.base import call_cached_tool


@traceable(name="attractions", run_type="tool")
async def search_attractions(city: str, category: str = "general") -> list[dict]:
    return await call_cached_tool(
        server_url=settings.MCP_ATTRACTIONS_SERVER_URL,
        tool_name="search_attractions",
        arguments={"city": city, "category": category},
        ttl_seconds=settings.ATTRACTIONS_CACHE_TTL_SECONDS,
    )
