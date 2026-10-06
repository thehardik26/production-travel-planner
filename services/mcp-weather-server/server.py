"""
mcp-weather-server - standalone, independently deployable MCP tool server.

Phase 4 changes this from the demo projects' pattern (an MCP server
started as a stdio subprocess, one-to-one with a single client process)
to an HTTP service any number of API instances can connect to at once.
That's the whole point of this phase: stdio is inherently single-client
(one pipe, one process on the other end); Streamable HTTP is a normal
HTTP endpoint, so it naturally serves many concurrent callers the same
way any web service does.

Tool logic (Open-Meteo geocoding + forecast, keyless) is ported unchanged
from mcptoolcalling/mcp_server/travel_tools_server.py's get_weather - only
the transport changed, not what the tool does or its schema. That's the
same point made in that file's docstring, one layer up: the caller only
ever depends on a tool's name/schema, never on how it's transported.

Run directly:
    python server.py
Or via Docker (see Dockerfile in this folder).

Configuration (env vars, see .env.example):
    MCP_WEATHER_HOST   default 0.0.0.0
    MCP_WEATHER_PORT   default 8001
"""

import os
from datetime import date as _date

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential_jitter

load_dotenv()

# Open-Meteo's free forecast endpoint only has data ~16 days ahead of
# "today". Asking for anything further out gets a raw 400 Bad Request
# from Open-Meteo itself - checking this BEFORE making the HTTP call
# means the caller (ResearchAgent) sees a clean, human-readable
# ValueError instead of an httpx.HTTPStatusError with a raw API URL in
# it, and we don't waste a network round-trip on a request that's
# guaranteed to fail.
MAX_FORECAST_DAYS_AHEAD = 16

HOST = os.getenv("MCP_WEATHER_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_WEATHER_PORT", "8001"))

# FastMCP reads host/port from its own constructor for streamable-http.
mcp = FastMCP("weather-tools", host=HOST, port=PORT)

_geocode_cache: dict[str, tuple[float, float]] = {}


def _is_nominatim_rate_limit(exc: BaseException) -> bool:
    """True only for Nominatim's rate-limit/bot-block responses (403,
    429). NOTE (19 Jul 2026): this server, mcp-hotels-server,
    mcp-attractions-server and mcp-transport-server each run as their
    OWN process with their OWN in-memory _geocode_cache - they don't
    share a cache. ResearchAgent (Phase 5) calls all of them
    concurrently via asyncio.gather, so a first-time lookup for the
    same city can hit Nominatim from 4 separate requests at nearly the
    same instant from this one machine's IP. Nominatim's usage policy
    caps this at ~1 req/sec and returns 403 when tripped. Retrying with
    a short exponential backoff + jitter is enough, because the 4
    requests don't retry in lockstep, so retries spread out and
    succeed. This is NOT retried for other errors (e.g. an unknown city
    returning empty results) - that's a bad request, not a transient
    one."""
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



def _weathercode_to_text(code: int) -> str:
    """Map Open-Meteo's WMO weather code to a simple condition string."""
    if code == 0:
        return "clear"
    if code in (1, 2, 3):
        return "cloudy"
    if code in (45, 48):
        return "foggy"
    # NOTE (21 Aug 2026): found via review - WMO codes 85/86 are "snow
    # showers" (https://open-meteo.com/en/docs, WMO Weather interpretation
    # codes table), but range(80, 87) is 80-86 inclusive, which swallowed
    # 85/86 into "rainy" before the snowy check below ever ran (this
    # function returns on the first match). A snow-shower forecast was
    # being shown to the user as rain. Snow codes (71-77 continuous snow,
    # plus 85/86 snow showers) are now checked together, and the rain
    # range is narrowed to just the rain-shower codes (80-82) it was
    # actually meant to cover.
    if code in range(51, 68) or code in (80, 81, 82):
        return "rainy"
    if code in range(71, 78) or code in (85, 86):
        return "snowy"
    if code in range(95, 100):
        return "stormy"
    return "windy"


@mcp.tool()
async def get_weather(city: str, date: str) -> dict:
    """Get a REAL weather forecast for a city on a given date (YYYY-MM-DD)
    via Open-Meteo. Open-Meteo only forecasts ~16 days ahead - dates
    further out will raise a clear error rather than return guessed data."""
    requested = _date.fromisoformat(date)
    days_ahead = (requested - _date.today()).days
    if days_ahead < 0:
        raise ValueError(f"Can't get a weather forecast for {date} - that date is in the past.")
    if days_ahead > MAX_FORECAST_DAYS_AHEAD:
        raise ValueError(
            f"Weather forecast for {date} isn't available yet - Open-Meteo only "
            f"forecasts about {MAX_FORECAST_DAYS_AHEAD} days ahead. Check back closer "
            f"to your trip for weather."
        )

    lat, lon = await _geocode(city)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": "auto",
                "start_date": date,
                "end_date": date,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    if date not in dates:
        raise ValueError(
            f"No forecast available for {date} (Open-Meteo covers ~16 days ahead)."
        )
    idx = dates.index(date)
    code = daily["weathercode"][idx]

    return {
        "city": city,
        "date": date,
        "condition": _weathercode_to_text(code),
        "temp_high_c": daily["temperature_2m_max"][idx],
        "temp_low_c": daily["temperature_2m_min"][idx],
        "precipitation_chance": daily["precipitation_probability_max"][idx],
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
