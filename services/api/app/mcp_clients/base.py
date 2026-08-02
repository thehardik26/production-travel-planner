"""
Generic "call an MCP tool over HTTP, through a Redis cache" building
block. Every per-server client (weather_client.py, and later
flights_client.py etc.) is a thin, typed wrapper around
`call_cached_tool()` - this file has zero knowledge of what a "flight"
or "hotel" is, only "server URL + tool name + arguments -> JSON result".

THE MULTI-USER STORY (this is the part worth remembering for an
interview):

1. Transport: `streamablehttp_client` opens a plain HTTP connection to
   an independently running MCP server. Unlike the demo projects' stdio
   subprocess (one pipe, one client, ever), any number of API request
   handlers - across any number of API replicas - can open one of these
   at the same time. The MCP server handles concurrency the same way
   any HTTP service does.

2. Caching is keyed by WHAT was asked, not WHO asked it. `_cache_key()`
   hashes the tool name + arguments only. That's deliberate: two
   different users asking "weather in Goa on 2026-08-01" should hit the
   exact same cache entry. This is what actually protects a rate-limited
   or slow upstream API (Duffel, Google Places, Open-Meteo) under real concurrent
   load - the first user's request pays the latency/quota cost, every
   other user asking the same question in the TTL window gets an
   instant cache hit. This only works because the underlying data
   (weather, flight prices) isn't user-specific - if a tool ever
   returns something personal, it must NOT be cached this way.

3. Redis (not an in-process dict) is what makes this cache shared
   correctly across multiple API replicas. An in-memory cache would
   give every replica its own cold cache and let N replicas each hit
   the upstream API once for the "same" question - Redis makes it one
   shared cache no matter how many API processes are running.

4. Failure handling: transient network failures (timeouts, connection
   refused) get up to 3 attempts with exponential backoff (see
   `_retry_on_transient_failure` below) before giving up - a brief
   upstream blip under load shouldn't fail a user's request outright.
   Non-transient failures (bad input, like an unknown city) are NOT
   retried, and once retries are exhausted the exception propagates up
   as a normal Python exception rather than hanging - callers (route
   handlers) decide how to respond (502, partial result), instead of
   this layer silently swallowing errors.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.redis_client import redis_client

# Retry only network-shaped failures (connection refused, timeout, DNS) -
# a handful of transient blips is normal when many concurrent users are
# hammering an upstream API. Do NOT retry ValueError (e.g. "unknown
# city", "no forecast for that date") - that's a bad request, retrying
# it just wastes the upstream API's rate-limit quota on a call that will
# fail identically every time.
_retry_on_transient_failure = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, TimeoutError, ConnectionError)),
)


def _cache_key(tool_name: str, arguments: dict[str, Any]) -> str:
    """Stable cache key from tool name + arguments - order-independent
    (sorted keys) so {"city": "Goa", "date": "x"} and {"date": "x",
    "city": "Goa"} hit the same entry."""
    payload = json.dumps(arguments, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{tool_name}:{payload}".encode()).hexdigest()
    return f"mcp:{tool_name}:{digest}"


@_retry_on_transient_failure
async def _call_tool_raw(server_url: str, tool_name: str, arguments: dict[str, Any]) -> Any:
    """Open a fresh MCP session over Streamable HTTP, call one tool,
    unwrap FastMCP's result shape. (Same unwrap logic as the stdio
    MCPToolClient in the demo projects - FastMCP wraps non-dict returns
    like list[dict] in {"result": [...]} because JSON Schema requires a
    top-level object; loosely-typed `dict` returns sometimes only show
    up as a JSON string in the text content block instead of
    structuredContent.)"""
    async with streamablehttp_client(server_url) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)

    if result.isError:
        # The tool raised on the SERVER side (bad input, missing API key,
        # upstream API down, etc.) - FastMCP reports this as isError=True
        # with the error message as plain text, NOT as a Python
        # exception on this side. Missing this check was a real bug:
        # the error text would fall through to the json.loads() attempt
        # below, fail to parse as JSON, and get returned as a bare
        # string - which then crashed far away (e.g. BudgetAgent doing
        # `f.get("price")` on a character of that string) with a
        # confusing "'str' object has no attribute 'get'" instead of a
        # clear error at the source.
        message = result.content[0].text if result.content else "unknown tool error"
        raise RuntimeError(f"{tool_name} failed on the server: {message}")

    if result.structuredContent is not None:
        data = result.structuredContent
        if isinstance(data, dict) and set(data.keys()) == {"result"}:
            return data["result"]
        return data

    if result.content:
        text = result.content[0].text
        try:
            return json.loads(text)
        except (json.JSONDecodeError, AttributeError):
            return text

    return None


async def call_cached_tool(
    server_url: str,
    tool_name: str,
    arguments: dict[str, Any],
    ttl_seconds: int,
) -> Any:
    """Cache-aside: check Redis, call the MCP server on a miss, store
    the result with a TTL. This is the one function every per-server
    client (weather_client.get_weather, etc.) calls."""
    key = _cache_key(tool_name, arguments)

    cached = await redis_client.get(key)
    if cached is not None:
        return json.loads(cached)

    result = await _call_tool_raw(server_url, tool_name, arguments)
    await redis_client.set(key, json.dumps(result), ex=ttl_seconds)
    return result
