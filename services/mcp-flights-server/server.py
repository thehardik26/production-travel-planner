"""
mcp-flights-server - standalone, independently deployable MCP tool server
for search_flights.

MIGRATED from Amadeus Self-Service to Duffel (19 Jul 2026): Amadeus
decommissioned its entire self-service developer portal on 17 Jul 2026 -
existing keys were disabled and new signups blocked. Duffel is the
modern equivalent: free "test mode" access token in ~1 minute at
https://app.duffel.com/join, no billing required. Test mode returns
offers from a fake airline ("Duffel Airways") so prices/schedules
aren't real-world accurate, but the API call, auth, and parsing are
genuinely live - same "test environment, real protocol" idea as
Amadeus's old sandbox.

IMPORTANT: this migration changed WHERE the data comes from and HOW
it's fetched, but not the tool's name or the shape of what it returns
(search_flights(origin, destination, date, passengers) -> list[dict]
with the same keys as before). Nothing on the API/agent side
(app/mcp_clients/flights_client.py, app/agents/*.py) needed to change -
exactly the point of putting a tool behind MCP instead of hardcoding
the data source into the caller.

Run directly:
    python server.py
Configuration (env vars, see .env.example):
    MCP_FLIGHTS_HOST, MCP_FLIGHTS_PORT, DUFFEL_API_KEY
"""

import os
import re

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

HOST = os.getenv("MCP_FLIGHTS_HOST", "0.0.0.0")
PORT = int(os.getenv("MCP_FLIGHTS_PORT", "8002"))

mcp = FastMCP("flights-tools", host=HOST, port=PORT)

DUFFEL_API_KEY = os.getenv("DUFFEL_API_KEY", "")
DUFFEL_BASE_URL = "https://api.duffel.com"

CITY_CODES = {
    "delhi": "DEL", "mumbai": "BOM", "goa": "GOI", "bangalore": "BLR",
    "bengaluru": "BLR", "chennai": "MAA", "kolkata": "CCU", "hyderabad": "HYD",
    "paris": "PAR", "london": "LON", "new york": "NYC", "dubai": "DXB",
    "tokyo": "TYO", "singapore": "SIN", "bangkok": "BKK", "bali": "DPS",
}


def _city_code(city: str) -> str:
    code = CITY_CODES.get(city.strip().lower())
    if not code:
        raise ValueError(f"No IATA code known for '{city}'. Add it to CITY_CODES in server.py.")
    return code


def _parse_iso_duration_minutes(duration: str) -> int:
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", duration or "")
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes


@mcp.tool()
async def search_flights(origin: str, destination: str, date: str, passengers: int = 1) -> list[dict]:
    """Search REAL flight offers via the Duffel API (test mode - free,
    no billing required). origin/destination are city names, resolved
    to IATA airport codes via CITY_CODES."""
    if not DUFFEL_API_KEY:
        raise RuntimeError(
            "DUFFEL_API_KEY not set. Sign up (free, ~1 min) at "
            "https://app.duffel.com/join, then create a test access token "
            "under Developers -> Access tokens, and put it in .env"
        )

    origin_code = _city_code(origin)
    destination_code = _city_code(destination)

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{DUFFEL_BASE_URL}/air/offer_requests",
            params={"return_offers": "true"},
            headers={
                "Authorization": f"Bearer {DUFFEL_API_KEY}",
                "Duffel-Version": "v2",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "data": {
                    "slices": [
                        {"origin": origin_code, "destination": destination_code, "departure_date": date}
                    ],
                    "passengers": [{"type": "adult"} for _ in range(max(1, passengers))],
                    "cabin_class": "economy",
                }
            },
        )
        if resp.status_code // 100 != 2:
            return []
        offers = resp.json().get("data", {}).get("offers", [])

    results = []
    for offer in offers:
        first_slice = offer["slices"][0]
        segments = first_slice["segments"]
        total_duration_minutes = sum(_parse_iso_duration_minutes(seg.get("duration")) for seg in segments)
        first_segment = segments[0]
        results.append({
            "airline": first_segment.get("operating_carrier", {}).get("name", "Unknown"),
            "origin": origin_code,
            "destination": destination_code,
            "date": date,
            "passengers": passengers,
            "stops": len(segments) - 1,
            "duration_minutes": total_duration_minutes,
            "price": float(offer["total_amount"]),
            "currency": offer["total_currency"],
        })
    return sorted(results, key=lambda f: f["price"])


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
