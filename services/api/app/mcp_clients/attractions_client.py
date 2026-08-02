"""Typed wrapper for the attractions MCP tool (mcp-attractions-server, OSM-backed)."""
from __future__ import annotations

from app.core.config import settings
from app.mcp_clients.base import call_cached_tool


async def search_attractions(city: str, category: str = "general") -> list[dict]:
    return await call_cached_tool(
        server_url=settings.MCP_ATTRACTIONS_SERVER_URL,
        tool_name="search_attractions",
        arguments={"city": city, "category": category},
        ttl_seconds=settings.ATTRACTIONS_CACHE_TTL_SECONDS,
    )
