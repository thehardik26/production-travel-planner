"""
mcp-attractions-server - standalone, independently deployable MCP tool
server for search_attractions (OpenStreetMap Nominatim + Overpass API,
free, no key). Same pattern as mcp-weather-server: Streamable HTTP
transport. Logic ported unchanged from
mcptoolcalling/mcp_server/travel_tools_server.py's search_attractions.

Run directly:
    python server.py
Configuration (env vars, see .env.example):
    MCP_ATTRACTIONS_HOST, MCP_ATTRACTIONS_PORT, OSM_USER_AGENT
"""

import os

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

load_dotenv()

HOST = os.getenv("MCP_ATTRACTIONS_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_ATTRACTIONS_PORT", "8004"))

mcp = FastMCP("attractions-tools", host=HOST, port=PORT)

OSM_USER_AGENT = os.getenv(
    "OSM_USER_AGENT", "mcp-attractions-server/1.0 (set OSM_USER_AGENT in .env)"
)

_geocode_cache: dict[str, tuple[float, float]] = {}

# NOTE (19 Jul 2026): overpass-api.de's main instance has been returning
# 406 Not Acceptable to many callers regardless of query correctness (a
# known, ongoing server-side issue - see
# https://github.com/drolbr/Overpass-API/issues/791), so it's listed
# last, as a last-resort fallback rather than primary. kumi.systems is
# a smaller community-run mirror and occasionally times out/drops the
# connection outright (httpx raises ConnectTimeout/ReadTimeout for
# that, which - unlike HTTPStatusError - often stringifies to an EMPTY
# string, so a failure there shows up as "...: )" with no detail).
# Trying multiple mirrors in order means one flaky mirror doesn't take
# the whole tool down.
_OVERPASS_MIRRORS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]


def _is_all_mirrors_failed(exc: BaseException) -> bool:
    """True when a full pass through every mirror came up empty. A 504
    (server overloaded) or a transient connect/read timeout is often
    gone a few seconds later - worth one more full pass through all 3
    mirrors before giving up and surfacing a failure to the user."""
    return isinstance(exc, RuntimeError)


@retry(
    reraise=True,
    stop=stop_after_attempt(2),
    wait=wait_exponential_jitter(initial=2, max=6),
    retry=retry_if_exception(_is_all_mirrors_failed),
)
async def _query_overpass(query: str) -> list[dict]:
    """POST an Overpass QL query, trying each mirror in _OVERPASS_MIRRORS
    in turn until one succeeds. If EVERY mirror fails in one pass, retry
    the whole pass once more after a short backoff (see
    _is_all_mirrors_failed) before finally raising the last error."""
    last_exc: BaseException | None = None
    async with httpx.AsyncClient(timeout=25, headers={"User-Agent": OSM_USER_AGENT}) as client:
        for url in _OVERPASS_MIRRORS:
            try:
                resp = await client.post(url, data={"data": query})
                resp.raise_for_status()
                return resp.json().get("elements", [])
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_exc = exc
                continue
    raise RuntimeError(
        f"All Overpass mirrors failed ({', '.join(_OVERPASS_MIRRORS)}). "
        f"Last error: {last_exc!r}"
    )


_CATEGORY_TAGS = {
    "general": '["tourism"~"attraction|viewpoint|artwork"]',
    "culture": '["tourism"~"museum|gallery"]',
    "adventure": '["leisure"~"sports_centre|water_park"]',
    "food": '["amenity"~"restaurant|cafe|marketplace"]',
}


def _is_nominatim_rate_limit(exc: BaseException) -> bool:
    """True only for Nominatim's rate-limit/bot-block responses (403,
    429). NOTE (19 Jul 2026): this server, mcp-weather-server,
    mcp-hotels-server and mcp-transport-server each run as their OWN
    process with their OWN in-memory _geocode_cache - they don't share
    a cache. ResearchAgent (Phase 5) calls all of them concurrently via
    asyncio.gather, so a first-time lookup for the same city can hit
    Nominatim from 4 separate requests at nearly the same instant from
    this one machine's IP. Nominatim's usage policy caps this at ~1
    req/sec and returns 403 when tripped. Retrying with a short
    exponential backoff + jitter is enough, because the 4 requests
    don't retry in lockstep, so retries spread out and succeed. This is
    NOT retried for other errors (e.g. an unknown city returning empty
    results) - that's a bad request, not a transient one."""
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (403, 429)


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=1, max=8),
    retry=retry_if_exception(_is_nominatim_rate_limit),
)
async def _geocode(city: str) -> tuple[float, float]:
    """City name -> (lat, lon) via OpenStreetMap Nominatim (free, no key)."""
    if city in _geocode_cache:
        return _geocode_cache[city]
    async with httpx.AsyncClient(headers={"User-Agent": OSM_USER_AGENT}, timeout=15) as client:
        resp = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": city, "format": "json", "limit": 1},
        )
        resp.raise_for_status()
        results = resp.json()
    if not results:
        raise ValueError(f"Could not geocode city '{city}' via Nominatim.")
    lat, lon = float(results[0]["lat"]), float(results[0]["lon"])
    _geocode_cache[city] = (lat, lon)
    return lat, lon


@mcp.tool()
async def search_attractions(city: str, category: str = "general") -> list[dict]:
    """List REAL points of interest in a city via OpenStreetMap (Overpass
    API, free, no API key), filtered by category (general, adventure,
    culture, food). OSM has no pricing/visit-duration data, so those
    fields are returned as None instead of invented."""
    lat, lon = await _geocode(city)
    tag_filter = _CATEGORY_TAGS.get(category, _CATEGORY_TAGS["general"])
    query = f'[out:json][timeout:20];(node{tag_filter}(around:6000,{lat},{lon}););out body 12;'

    elements = await _query_overpass(query)

    results = []
    for el in elements:
        name = el.get("tags", {}).get("name")
        if not name:
            continue
        results.append({
            "name": name,
            "city": city,
            "category": category,
            "avg_visit_hours": None,
            "price": None,
            "currency": "USD",
            "rating": None,
        })
    return results[:10]


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
