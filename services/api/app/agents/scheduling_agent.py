"""
SchedulingAgent - the other agent that genuinely needs an LLM: turning a
pile of research results (attractions, weather, transport options) into
a coherent day-by-day plan is a language/reasoning task, not arithmetic.
Same resilience pattern as IntentAgent: if the LLM call fails, fall back
to a deterministic round-robin scheduler instead of failing the whole
trip-planning request.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from app.core.llm import chat_json
from app.orchestration.state import TripPlanningState

_SYSTEM_PROMPT = """You are a travel scheduling assistant. Given trip \
details and research results (weather, attractions, transport options), \
produce a day-by-day itinerary as a single JSON object with this shape:

{
  "days": [
    {"date": "YYYY-MM-DD", "summary": "short description of the day", \
"activities": ["activity 1", "activity 2"]}
  ],
  "notes": "short overall note, e.g. a weather advisory or budget note"
}

Only use attraction/transport names given in the input - do not invent \
new places. If attractions are limited, it's fine to repeat a light day \
or suggest free time. Respond with ONLY the JSON object, no other text."""


def _fallback_itinerary(start_str: str | None, end_str: str | None, attractions: list[dict]) -> dict:
    """Deterministic round-robin scheduler used when the LLM is
    unavailable - no creativity, but never fails and never invents data
    that wasn't in `attractions`."""
    if not start_str or not end_str:
        return {"days": [], "notes": "Insufficient date info to build a schedule."}

    start = date.fromisoformat(start_str)
    end = date.fromisoformat(end_str)
    n_days = max(1, (end - start).days + 1)

    days = []
    for i in range(n_days):
        day_date = (start + timedelta(days=i)).isoformat()
        day_attractions = [a["name"] for j, a in enumerate(attractions) if j % n_days == i]
        days.append({
            "date": day_date,
            "summary": f"Day {i + 1}",
            "activities": day_attractions or ["Free day - explore locally"],
        })
    return {"days": days, "notes": "Generated via rule-based fallback (LLM unavailable)."}


class SchedulingAgent:
    async def run(self, state: TripPlanningState) -> dict:
        errors = list(state.get("errors", []))
        start = state.get("start_date")
        end = state.get("end_date")
        attractions = state.get("attractions") or []

        try:
            payload = {
                "destination": state.get("destination"),
                "start_date": start,
                "end_date": end,
                "travelers": state.get("travelers"),
                "preferences": state.get("preferences"),
                "weather": state.get("weather"),
                "attractions": attractions[:10],
                "transport": (state.get("transport") or [])[:5],
            }
            itinerary = await chat_json(_SYSTEM_PROMPT, json.dumps(payload, default=str))
        except Exception as exc:
            errors.append(f"SchedulingAgent: LLM scheduling failed ({exc}), used round-robin fallback")
            itinerary = _fallback_itinerary(start, end, attractions)

        return {"itinerary": itinerary, "errors": errors}
