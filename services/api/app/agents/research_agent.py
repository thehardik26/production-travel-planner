"""
ResearchAgent - calls all five MCP tools (through the cached HTTP
clients built in Phase 4) IN PARALLEL via asyncio.gather, not one after
another. Sequentially, five ~200-500ms tool calls would add up to
seconds of latency per planning request; in parallel they take as long
as the slowest one.

PARTIAL-FAILURE HANDLING is the important design decision here: each
tool call is wrapped so one failing tool (e.g. flights, if
AMADEUS_API_KEY isn't set) does not take down the whole research step.
A trip with no flight data is still useful to show the user (weather,
attractions, hotels); a trip that 500s because one of five tools was
briefly unavailable is not. Failures are recorded in state["errors"] so
they're visible, not silently dropped.
"""
from __future__ import annotations

import asyncio

from app.mcp_clients import attractions_client, flights_client, hotels_client, transport_client, weather_client
from app.orchestration.state import TripPlanningState


async def _safe(name: str, coro) -> tuple[str, object, str | None]:
    try:
        return name, await coro, None
    except Exception as exc:
        return name, None, str(exc)


class ResearchAgent:
    async def run(self, state: TripPlanningState) -> dict:
        destination = state.get("destination")
        origin = state.get("origin")
        start_date = state.get("start_date")
        end_date = state.get("end_date")
        travelers = state.get("travelers") or 1
        errors = list(state.get("errors", []))

        tasks = [_safe("weather", weather_client.get_weather(destination, start_date))]
        if origin:
            tasks.append(_safe("flights", flights_client.search_flights(origin, destination, start_date, travelers)))
        tasks.append(_safe("hotels", hotels_client.search_hotels(destination, start_date, end_date, travelers)))
        tasks.append(_safe("attractions", attractions_client.search_attractions(destination)))
        tasks.append(_safe("transport", transport_client.search_transport(destination)))

        results = await asyncio.gather(*tasks)

        update: dict = {"weather": None, "flights": [], "hotels": [], "attractions": [], "transport": []}
        for name, value, err in results:
            if err is not None:
                errors.append(f"ResearchAgent: {name} failed ({err})")
            else:
                update[name] = value

        update["errors"] = errors
        return update
