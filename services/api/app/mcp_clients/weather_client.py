"""
Typed wrapper for the weather MCP tool. Route handlers / agents call
`get_weather(city, date)` and never see the cache key, the HTTP
transport, or the MCP session handshake underneath - same principle as
the demo projects: callers depend on a tool's name and shape, not on
how it's fetched.
"""
from __future__ import annotations

from app.core.config import settings
from app.mcp_clients.base import call_cached_tool


async def get_weather(city: str, date: str) -> dict:
    return await call_cached_tool(
        server_url=settings.MCP_WEATHER_SERVER_URL,
        tool_name="get_weather",
        arguments={"city": city, "date": date},
        ttl_seconds=settings.WEATHER_CACHE_TTL_SECONDS,
    )
