"""Typed wrapper for the flights MCP tool (mcp-flights-server, Duffel-backed)."""
from __future__ import annotations

from app.core.config import settings
from app.mcp_clients.base import call_cached_tool


async def search_flights(origin: str, destination: str, date: str, passengers: int = 1) -> list[dict]:
    return await call_cached_tool(
        server_url=settings.MCP_FLIGHTS_SERVER_URL,
        tool_name="search_flights",
        arguments={"origin": origin, "destination": destination, "date": date, "passengers": passengers},
        ttl_seconds=settings.FLIGHTS_CACHE_TTL_SECONDS,
    )
