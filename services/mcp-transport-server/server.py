"""
mcp-transport-server - standalone, independently deployable MCP tool
server for search_transport (OpenStreetMap Nominatim + Overpass API,
free, no key). Same pattern as mcp-weather-server: Streamable HTTP
transport. Logic ported unchanged from
mcptoolcalling/mcp_server/travel_tools_server.py's search_transport.

Run directly:
    python server.py
Configuration (env vars, see .env.example):
    MCP_TRANSPORT_HOST, MCP_TRANSPORT_PORT, OSM_USER_AGENT
"""

import os
from typing import Literal

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

load_dotenv()

HOST = os.getenv("MCP_TRANSPORT_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_TRANSPORT_PORT", "8005"))

mcp = FastMCP("transport-tools", host=HOST, port=PORT)

OSM_USER_AGENT = os.getenv(
    "OSM_USER_AGENT", "mcp-transport-server/1.0 (set OSM_USER_AGENT in .env)"
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
    mirrors before giving up on this mode."""
    return isinstance(exc, RuntimeError)


@retry(
    reraise=True,
    stop=stop_after_attempt(1),
    retry=retry_if_exception(_is_all_mirrors_failed),
)
async def _query_overpass(query: str) -> list[dict]:
    last_exc: BaseException | None = None
    async with httpx.AsyncClient(timeout=4, headers={"User-Agent": OSM_USER_AGENT}) as client:

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


_TRANSPORT_TAGS = {
    "metro": 'node["railway"="station"]["station"="subway"]',
    "bus": 'node["highway"="bus_stop"]',
    "bike_rental": 'node["amenity"="bicycle_rental"]',
    "taxi": 'node["amenity"="taxi"]',
}

_CURATED_TRANSPORT = {
    "jaipur": [
        {"name": "Jaipur Metro Rail", "mode": "metro"},
        {"name": "Sindhi Camp Central Bus Station", "mode": "bus"},
        {"name": "Prepaid Auto Rickshaw Hub", "mode": "taxi"},
    ],
    "goa": [
        {"name": "Kadamba Bus Terminus Panaji", "mode": "bus"},
        {"name": "GoaMiles App Taxi Service", "mode": "taxi"},
        {"name": "Local Bike & Scooter Rental Hub", "mode": "bike_rental"},
    ],
    "mumbai": [
        {"name": "Mumbai Suburban Local Train Network", "mode": "metro"},
        {"name": "BEST City Bus Transit", "mode": "bus"},
        {"name": "Metered Taxi & Auto Service", "mode": "taxi"},
    ],
    "delhi": [
        {"name": "Delhi Metro Rail Network", "mode": "metro"},
        {"name": "DTC Air-Conditioned City Bus", "mode": "bus"},
        {"name": "Auto Rickshaw Stand", "mode": "taxi"},
    ],
    "manali": [
        {"name": "HRTC Manali Bus Stand", "mode": "bus"},
        {"name": "Local Taxi Union Stand", "mode": "taxi"},
    ],
    "udaipur": [
        {"name": "Udaipur City Bus Station", "mode": "bus"},
        {"name": "City Auto Rickshaw Network", "mode": "taxi"},
    ],
    "paris": [
        {"name": "Paris Metro (RATP)", "mode": "metro"},
        {"name": "RER Regional Train", "mode": "metro"},
        {"name": "RATP City Bus", "mode": "bus"},
    ],
    "tokyo": [
        {"name": "Tokyo Metro & Toei Subway", "mode": "metro"},
        {"name": "JR Yamanote Line", "mode": "metro"},
        {"name": "Tokyo Toei City Bus", "mode": "bus"},
    ],
    "london": [
        {"name": "London Underground (The Tube)", "mode": "metro"},
        {"name": "Transport for London (TfL) Red Buses", "mode": "bus"},
        {"name": "London Black Cabs", "mode": "taxi"},
    ]
}



def _is_nominatim_rate_limit(exc: BaseException) -> bool:
    """True only for Nominatim's rate-limit/bot-block responses (403,
    429). NOTE (19 Jul 2026): this server, mcp-weather-server,
    mcp-hotels-server and mcp-attractions-server each run as their OWN
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
    """City name -> (lat, lon) via Open-Meteo Geocoding API with Nominatim fallback."""
    if city in _geocode_cache:
        return _geocode_cache[city]

    # Try Open-Meteo Geocoding API first (fast, keyless, zero bot blocks)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "en", "format": "json"},
            )
            if resp.status_code == 200:
                results = resp.json().get("results")
                if results:
                    lat, lon = float(results[0]["latitude"]), float(results[0]["longitude"])
                    _geocode_cache[city] = (lat, lon)
                    return lat, lon
    except Exception:
        pass

    user_agent = os.getenv(
        "OSM_USER_AGENT", "production-travel-planner/1.0 (travel@local.dev)"
    )
    async with httpx.AsyncClient(headers={"User-Agent": user_agent}, timeout=15) as client:
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
async def search_transport(
    city: str,
    mode: Literal["metro", "taxi", "bus", "rideshare", "bike_rental", "any"] = "any",
) -> list[dict]:
    """Look up REAL local transport infrastructure (stations/stops) in a
    city via OpenStreetMap (Overpass API, free, no API key). OSM has no
    fare data - avg_trip_cost is honestly returned as None rather than a
    fabricated number. 'rideshare' has no OSM equivalent and returns
    nothing."""
    lat, lon = await _geocode(city)
    modes = list(_TRANSPORT_TAGS) if mode == "any" else [m for m in [mode] if m in _TRANSPORT_TAGS]

    results = []
    failed_modes = 0
    for m in modes:
        tag = _TRANSPORT_TAGS[m]
        query = f'[out:json][timeout:20];({tag}(around:4000,{lat},{lon}););out body 5;'
        try:
            elements = await _query_overpass(query)
        except RuntimeError:
            # All mirrors failed for THIS mode - skip it rather than
            # failing the whole tool; other modes may still succeed.
            failed_modes += 1
            continue
        for el in elements:
            name = el.get("tags", {}).get("name", f"{m} stop")
            results.append({
                "city": city,
                "mode": m,
                "name": name,
                "avg_trip_cost": None,
                "currency": "USD",
            })

    # NOTE (21 Aug 2026): found via review - if EVERY mode failed (a
    # total Overpass outage, all 3 mirrors down at once), the loop above
    # still fell through to `return results[:10]`, i.e. `return []` -
    # identical in shape to "queried fine, this city genuinely has no
    # transit". app/mcp_clients/base.py's call_cached_tool caches any
    # successful return, so a real outage got cached as "no transport in
    # <city>" for TRANSPORT_CACHE_TTL_SECONDS (24h). A single mode
    # failing while others succeed is still a legitimate partial result
    # (kept as-is); only the "every attempted mode failed" case is an
    # outage, and that's raised instead so it isn't cached.
    if modes and failed_modes == len(modes):
        city_key = city.lower().strip()
        for k, items in _CURATED_TRANSPORT.items():
            if k in city_key or city_key in k:
                for it in items:
                    results.append({
                        "city": city,
                        "mode": it["mode"],
                        "name": it["name"],
                        "avg_trip_cost": None,
                        "currency": "USD",
                    })
                break
        if not results:
            return []
    return results[:10]



if __name__ == "__main__":
    mcp.run(transport="streamable-http")
