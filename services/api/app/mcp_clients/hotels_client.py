"""Typed wrapper for the hotels MCP tool (mcp-hotels-server, Google Places-backed)."""
from __future__ import annotations

from app.core.config import settings
from app.mcp_clients.base import call_cached_tool


async def search_hotels(city: str, check_in: str, check_out: str, guests: int = 1) -> list[dict]:
    return await call_cached_tool(
        server_url=settings.MCP_HOTELS_SERVER_URL,
        tool_name="search_hotels",
        arguments={"city": city, "check_in": check_in, "check_out": check_out, "guests": guests},
        ttl_seconds=settings.HOTELS_CACHE_TTL_SECONDS,
    )
