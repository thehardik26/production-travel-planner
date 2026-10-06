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

Phase 6 adds a sixth concurrent lookup: the RAG destination-guide
retrieval (app/rag/destination_guide.py). It's not an MCP tool - no
network hop, no separate deployable service - but it's wrapped in the
exact same `_safe()` pattern as the five real tools because it fails
the same way they do from this agent's point of view (an embedding
model that hasn't loaded yet, an unreachable Qdrant, a destination with
no guide coverage) and a trip should plan just fine without it.
"""
from __future__ import annotations

import asyncio

from app.mcp_clients import attractions_client, flights_client, hotels_client, transport_client, weather_client
from app.orchestration.state import TripPlanningState
from app.rag.destination_guide import get_destination_guide


async def _safe(name: str, coro) -> tuple[str, object, str | None]:
    try:
        return name, await coro, None
    except Exception as exc:
        return name, None, str(exc)


# NOTE (21 Aug 2026): found via a real user report - the raw
# f"ResearchAgent: {name} failed ({err})" format put an internal class
# name ("ResearchAgent") and the mechanical word "failed" in front of a
# message that (after mcp_clients/base.py's own cleanup - see its NOTE)
# is already a complete, readable sentence on its own, e.g. "Weather
# forecast for 2026-10-05 isn't available yet - Open-Meteo only
# forecasts about 16 days ahead." Wrapping that in "ResearchAgent:
# weather failed (...)" made a normal, expected degradation read like an
# unhandled backend exception. A short, human-facing category label
# instead of the raw internal node/tool name keeps "which part of the
# plan is this about" without the implementation-detail flavor.
_SOURCE_LABELS = {
    "weather": "Weather",
    "flights": "Flights",
    "hotels": "Hotels",
    "attractions": "Attractions",
    "transport": "Transport",
    "destination_guide": "Destination guide",
}


class ResearchAgent:
    async def run(self, state: TripPlanningState) -> dict:
        destination = state.get("destination")
        origin = state.get("origin")
        start_date = state.get("start_date")
        end_date = state.get("end_date")
        travelers = state.get("travelers") or 1
        preferences = state.get("preferences") or []
        errors = list(state.get("errors", []))

        tasks = [_safe("weather", weather_client.get_weather(destination, start_date))]
        if origin:
            tasks.append(_safe("flights", flights_client.search_flights(origin, destination, start_date, travelers)))
        tasks.append(_safe("hotels", hotels_client.search_hotels(destination, start_date, end_date, travelers)))
        tasks.append(_safe("attractions", attractions_client.search_attractions(destination)))
        tasks.append(_safe("transport", transport_client.search_transport(destination)))
        tasks.append(_safe("destination_guide", get_destination_guide(destination, preferences)))

        results = await asyncio.gather(*tasks)

        update: dict = {
            "weather": None, "flights": [], "hotels": [], "attractions": [], "transport": [],
            "destination_guide": None,
        }
        for name, value, err in results:
            if err is not None:
                label = _SOURCE_LABELS.get(name, name.replace("_", " ").title())
                # Some upstream messages already open with the same word
                # as the label (e.g. "Weather forecast for ... isn't
                # available yet...") - prefixing "Weather: " onto that
                # reads as a stutter ("Weather: Weather forecast..."). A
                # message that already identifies itself doesn't need
                # the label restated; anything more generic still gets
                # it for context.
                errors.append(err if err.lower().startswith(label.lower()) else f"{label}: {err}")
            else:
                update[name] = value

        update["errors"] = errors
        return update
