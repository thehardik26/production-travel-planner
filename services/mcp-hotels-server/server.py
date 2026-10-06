"""
mcp-hotels-server - standalone, independently deployable MCP tool server
for search_hotels.

MIGRATED from Amadeus Self-Service to Google Places API - Nearby Search
(19 Jul 2026): Amadeus decommissioned its self-service portal on 17 Jul
2026. Duffel Stays (the natural Duffel equivalent for hotels) requires
requesting access and manual approval, not instant self-serve, so it
wasn't usable right now. Google Places API is: real hotel data
(name, address, rating), free monthly credit, no approval wait -
signup is a Google Cloud project + billing account (a card is required
to enable billing even though usage stays within the free credit for
this project's volume).

HONESTY NOTE (same pattern as the attractions/transport tools): Google
Places does not return live room pricing. price / price_per_night are
returned as None rather than invented - BudgetAgent (Phase 5) already
handles a missing hotel price gracefully (see
app/agents/budget_agent.py's `missing_estimates` field).

Run directly:
    python server.py
Configuration (env vars, see .env.example):
    MCP_HOTELS_HOST, MCP_HOTELS_PORT, GOOGLE_PLACES_API_KEY, OSM_USER_AGENT
"""

import os
from datetime import datetime

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

load_dotenv()

HOST = os.getenv("MCP_HOTELS_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_HOTELS_PORT", "8003"))

mcp = FastMCP("hotels-tools", host=HOST, port=PORT)

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
OSM_USER_AGENT = os.getenv(
    "OSM_USER_AGENT", "mcp-hotels-server/1.0 (set OSM_USER_AGENT in .env)"
)

_geocode_cache: dict[str, tuple[float, float]] = {}


def _is_nominatim_rate_limit(exc: BaseException) -> bool:
    """True only for Nominatim's rate-limit/bot-block responses (403,
    429). NOTE (19 Jul 2026): this MCP server, mcp-weather-server,
    mcp-attractions-server and mcp-transport-server each run as their
    OWN process with their OWN in-memory _geocode_cache - they don't
    share a cache. ResearchAgent (Phase 5) calls all of them
    concurrently via asyncio.gather, so a first-time lookup for the
    same city (e.g. "Goa") can hit Nominatim from 4 separate requests
    at nearly the same instant from this one machine's IP. Nominatim's
    usage policy caps this at ~1 req/sec and returns 403 when tripped.
    Retrying with a short exponential backoff + jitter is enough,
    because the 4 requests don't retry in lockstep, so retries spread
    out and succeed. This is NOT retried for other errors (e.g. an
    unknown city returning empty results) - that's a bad request, not
    a transient one."""
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
async def search_hotels(city: str, check_in: str, check_out: str, guests: int = 1) -> list[dict]:
    """Search REAL hotels near a city via Google Places API (Nearby
    Search, type=lodging). No live room pricing is available from this
    source - price/price_per_night are honestly None, not invented."""
    if not GOOGLE_PLACES_API_KEY:
        raise RuntimeError(
            "GOOGLE_PLACES_API_KEY not set. Create one at "
            "https://console.cloud.google.com (enable 'Places API (New)' "
            "on a project with billing enabled - free monthly credit "
            "covers normal dev/demo usage) and put it in .env"
        )

    lat, lon = await _geocode(city)
    # NOTE (21 Aug 2026): found via review - this used to be
    # `max(1, (check_out - check_in).days)`, which silently turned a
    # REVERSED date range (check_out before check_in - a genuine bad
    # request, e.g. a form bug or a user typo) into a confident "1
    # night" instead of surfacing the mistake.
    #
    # NOTE (21 Aug 2026, second pass): the first fix over-corrected -
    # it rejected check_in == check_out (0 nights) as an error too, but
    # that's not a mistake, it's a real, common request: a same-day trip
    # ("1 day trip to Mumbai") has no separate checkout date at all.
    # Someone planning a day trip might still want to see nearby hotel
    # options (in case they decide to stay), so this should default to
    # showing 1 night of options - exactly like before - not error out
    # and take the whole hotels search down with it. Only a GENUINELY
    # reversed range (checkout before check-in - impossible, not just
    # "0 nights") is an actual bad request worth rejecting.
    nights = (datetime.fromisoformat(check_out) - datetime.fromisoformat(check_in)).days
    if nights < 0:
        raise ValueError(
            f"check_out ({check_out}) is before check_in ({check_in}) - check the dates."
        )
    nights = max(1, nights)

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://places.googleapis.com/v1/places:searchNearby",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
                "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating",
            },
            json={
                "includedTypes": ["lodging"],
                "maxResultCount": 10,
                "locationRestriction": {
                    "circle": {"center": {"latitude": lat, "longitude": lon}, "radius": 5000.0}
                },
            },
        )
        if resp.status_code // 100 != 2:
            # NOTE (19 Jul 2026): resp.raise_for_status() alone only
            # surfaces the status code ("403 Forbidden"), not Google's
            # response body - which is where the actual reason lives
            # (API key restricted to wrong APIs/referrers, billing not
            # enabled, project not activated, etc). Surfacing the body
            # here turns "403 Forbidden" into an actionable message.
            raise RuntimeError(
                f"Google Places searchNearby returned {resp.status_code}: {resp.text}"
            )
        places = resp.json().get("places", [])

    results = []
    for p in places:
        results.append({
            "name": p.get("displayName", {}).get("text", "Unknown Hotel"),
            "city": city,
            "check_in": check_in,
            "check_out": check_out,
            "nights": nights,
            "guests": guests,
            "rating": p.get("rating"),
            "price_per_night": None,
            "price": None,
            "currency": "USD",
        })
    return results


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
