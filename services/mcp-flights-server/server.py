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
    # Added 21 Aug 2026 - these are real IATA-served Indian cities that
    # kept showing up in trip requests but weren't in the original list
    # (found via "No IATA code known for 'Udaipur'" failing a real
    # search). Each of these has its own airport.
    "pune": "PNQ", "jaipur": "JAI", "udaipur": "UDR", "agra": "AGR",
    "shimla": "SLV", "pondicherry": "PNY",
    # Added 21 Aug 2026 (second pass) - same story as above, this time
    # found via "No IATA code known for 'Chandigarh'" (a real ORIGIN
    # city in a trip request, not just destinations - _city_code() is
    # called on both). Rounding out the rest of India's major
    # metro/state-capital airports up front rather than adding them one
    # failed search at a time.
    "chandigarh": "IXC", "amritsar": "ATQ", "srinagar": "SXR", "leh": "IXL",
    "varanasi": "VNS", "lucknow": "LKO", "patna": "PAT", "guwahati": "GAU",
    "bhubaneswar": "BBI", "indore": "IDR", "nagpur": "NAG", "raipur": "RPR",
    "bhopal": "BHO", "vadodara": "BDQ", "surat": "STV", "ranchi": "IXR",
    "visakhapatnam": "VTZ", "trivandrum": "TRV", "thiruvananthapuram": "TRV",
    "madurai": "IXM", "mangalore": "IXE", "coimbatore": "CJB",
    "nashik": "ISK", "rajkot": "RAJ", "jodhpur": "JDH", "jammu": "IXJ",
    "dehradun": "DED", "port blair": "IXZ", "imphal": "IMF",
    # These destinations don't have their own commercial airport - mapped
    # to the nearest one instead, same as how a traveler would actually
    # fly there. The result's "destination" will show that nearer
    # airport's code, not the town itself - a known tradeoff, not a bug.
    "manali": "KUU",       # Kullu-Manali (Bhuntar) airport, ~50km away
    "lonavala": "PNQ",     # nearest is Pune, ~65km away
    "kerala": "COK",       # Kochi, the main gateway for the state
    "munnar": "COK",       # nearest airport is Kochi, ~110km away
    "ooty": "CJB",         # nearest is Coimbatore, ~85km away
    "darjeeling": "IXB",   # nearest is Bagdogra, ~65km away
    "rishikesh": "DED",    # nearest is Dehradun (Jolly Grant), ~20km away
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
            # NOTE (21 Aug 2026): found via review - this used to just
            # `return []` here, which looks identical to "Duffel searched
            # and genuinely found zero flights". The caller
            # (app/mcp_clients/base.py's call_cached_tool) caches
            # whatever a successful call returns, so a transient Duffel
            # error (bad/expired token, rate limit, an outage) got cached
            # as a confident "no flights on this route" for
            # FLIGHTS_CACHE_TTL_SECONDS - hiding the real problem and
            # blocking every other user asking about the same route
            # until the cache entry expired. Raising instead means
            # call_cached_tool never caches it, ResearchAgent's existing
            # per-tool error handling records a warning like normal, and
            # the NEXT request tries again instead of being stuck.
            raise RuntimeError(
                f"Duffel offer_requests returned {resp.status_code}: {resp.text}"
            )
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
            # NOTE (21 Aug 2026): the actual Duffel request above already
            # clamps to max(1, passengers) since Duffel rejects a
            # zero/negative passenger count - but this output row was
            # still echoing back the raw, unclamped input. A caller that
            # passed passengers=0 would get results that genuinely
            # reflect a 1-adult search while every row claimed
            # "passengers: 0", which is just wrong, not a rounding
            # nuance.
            "passengers": max(1, passengers),
            "stops": len(segments) - 1,
            "duration_minutes": total_duration_minutes,
            "price": float(offer["total_amount"]),
            "currency": offer["total_currency"],
        })
    return sorted(results, key=lambda f: f["price"])


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
