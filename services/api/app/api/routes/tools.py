"""
Demo/proof routes for Phase 4: an authenticated user calling an MCP tool
through the cached HTTP client. Not the final trip-planning endpoint
(that's Phase 5, once LangGraph agents call these same mcp_clients) -
these routes exist so the whole chain (JWT auth -> rate limit -> MCP
HTTP call -> Redis cache) is reachable and testable over real HTTP
right now, end to end, for all five tools.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.models import User
from app.mcp_clients import attractions_client, flights_client, hotels_client, transport_client, weather_client

router = APIRouter(prefix="/api/tools", tags=["tools"])


def _tool_call_failed(name: str, exc: Exception) -> HTTPException:
    # Every route below hits this on any failure from its MCP server or
    # that server's upstream API - one place decides "the thing we
    # depend on failed" becomes a clean 502, not a raw 500 traceback.
    #
    # NOTE (19 Jul 2026): when the MCP server for this tool is
    # unreachable (not running, crashed, wrong port), the mcp SDK's
    # streamablehttp_client fails inside its own internal anyio
    # TaskGroup, so what reaches here isn't the real network error but
    # a (Base)ExceptionGroup whose str() is just "unhandled errors in a
    # TaskGroup (N sub-exception(s))" - useless for debugging. Unwrap it
    # down to the actual leaf exception(s) so the 502 detail says what
    # really failed (e.g. "Connection refused" -> that MCP server just
    # isn't running).
    if isinstance(exc, BaseExceptionGroup):
        leaves = exc.exceptions
        while len(leaves) == 1 and isinstance(leaves[0], BaseExceptionGroup):
            leaves = leaves[0].exceptions
        exc = leaves[0] if len(leaves) == 1 else exc
    return HTTPException(status_code=502, detail=f"{name} tool call failed: {exc}")


@router.get("/weather")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def get_weather_tool(
    request: Request,  # required by @limiter.limit - slowapi reads the client IP off it
    city: str,
    date: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Protected + rate-limited + cached. Try calling this twice in a row
    with the same city/date - the second call is served from Redis
    instead of hitting the MCP server again."""
    try:
        return await weather_client.get_weather(city=city, date=date)
    except Exception as exc:
        raise _tool_call_failed("weather", exc) from exc


@router.get("/flights")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def search_flights_tool(
    request: Request,
    origin: str,
    destination: str,
    date: str,
    passengers: int = 1,
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Needs AMADEUS_API_KEY/SECRET set on mcp-flights-server - without
    them this returns a 502 with a clear message, not a silent failure."""
    try:
        return await flights_client.search_flights(origin, destination, date, passengers)
    except Exception as exc:
        raise _tool_call_failed("flights", exc) from exc


@router.get("/hotels")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def search_hotels_tool(
    request: Request,
    city: str,
    check_in: str,
    check_out: str,
    guests: int = 1,
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Needs AMADEUS_API_KEY/SECRET set on mcp-hotels-server."""
    try:
        return await hotels_client.search_hotels(city, check_in, check_out, guests)
    except Exception as exc:
        raise _tool_call_failed("hotels", exc) from exc


@router.get("/attractions")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def search_attractions_tool(
    request: Request,
    city: str,
    category: str = "general",
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Keyless (OpenStreetMap) - no API key setup needed to try this one."""
    try:
        return await attractions_client.search_attractions(city, category)
    except Exception as exc:
        raise _tool_call_failed("attractions", exc) from exc


@router.get("/transport")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def search_transport_tool(
    request: Request,
    city: str,
    mode: str = "any",
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Keyless (OpenStreetMap) - no API key setup needed to try this one."""
    try:
        return await transport_client.search_transport(city, mode)
    except Exception as exc:
        raise _tool_call_failed("transport", exc) from exc
