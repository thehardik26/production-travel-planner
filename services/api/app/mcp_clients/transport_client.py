"""Typed wrapper for the transport MCP tool (mcp-transport-server, OSM-backed)."""
from __future__ import annotations

from app.core.config import settings
from app.mcp_clients.base import call_cached_tool


async def search_transport(city: str, mode: str = "any") -> list[dict]:
    return await call_cached_tool(
        server_url=settings.MCP_TRANSPORT_SERVER_URL,
        tool_name="search_transport",
        arguments={"city": city, "mode": mode},
        ttl_seconds=settings.TRANSPORT_CACHE_TTL_SECONDS,
    )
