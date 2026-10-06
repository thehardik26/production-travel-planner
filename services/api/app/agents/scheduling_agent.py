"""
SchedulingAgent - the other agent that genuinely needs an LLM: turning a
pile of research results (attractions, weather, transport options) into
a coherent day-by-day plan is a language/reasoning task, not arithmetic.
Same resilience pattern as IntentAgent: if the LLM call fails, fall back
to a deterministic round-robin scheduler instead of failing the whole
trip-planning request.

Phase 6 adds `destination_guide` (RAG passages, see
app/rag/destination_guide.py) as extra context for both paths: the LLM
prompt allows it to ground the day-by-day "summary" text in real local
detail (best time of day for a viewpoint, a dish worth trying) even
when the OSM attractions tool came back thin or empty, and the
rule-based fallback pulls a short line out of the guide instead of the
old generic "Free day - explore locally" for any day that has no real
attraction data to schedule.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

from app.core.llm import chat_json
from app.orchestration.state import TripPlanningState

# NOTE (21 Aug 2026): found via a real user report ("itinerary is too
# bad... naive level implementation"). The prompt used to forbid the LLM
# from ever scheduling a named place unless it came from the "attractions"
# list (OSM data) - even when destination_guide (the hand-curated RAG
# text) explicitly named a real, well-known place (e.g. Goa's "Basilica
# of Bom Jesus", "Baga Beach"). Combined with OSM's attractions coverage
# being thin/noisy for some destinations (see mcp-attractions-server's
# 21 Aug 2026 NOTE on the artwork tag and state-vs-city geocoding), this
# meant good, real, trustworthy data sat unused and itineraries leaned on
# generic filler ("wander the old town markets") more than they needed
# to. destination_guide is static, reviewed text (not LLM-generated, not
# live/uncertain like a tool call) - safe to treat as a second source of
# real place names, not just background color.
_SYSTEM_PROMPT = """You are a travel scheduling assistant. Given trip \
details and research results (weather, attractions, transport options, \
and destination-guide background reading), produce a day-by-day \
itinerary as a single JSON object with this shape:

{
  "days": [
    {"date": "YYYY-MM-DD", "summary": "short description of the day", \
"activities": [
      {"time": "08:00", "activity": "Breakfast at the hotel"},
      {"time": "10:00", "activity": "..."},
      {"time": "13:00", "activity": "Lunch at ..."},
      {"time": "16:00", "activity": "..."},
      {"time": "19:30", "activity": "Dinner at ..."}
    ]}
  ],
  "notes": "short overall note, e.g. a weather advisory or budget note"
}

Give each day 4-6 activities, in "HH:MM" 24-hour time, spanning morning \
through evening - always include a breakfast, lunch and dinner slot (a \
generic one like "Breakfast at the hotel" is fine if no specific \
restaurant is known), not just sightseeing. Named stops should mainly \
come from the "attractions"/"transport" lists given in the input - do \
not invent a place name that appears in neither those lists NOR the \
"destination_guide" text. The "destination_guide" field, when present, \
is real, hand-curated background reading about this destination (not \
generated, not a guess) - if it explicitly names a specific place \
(a beach, landmark, market, neighborhood, etc.) that isn't already in \
"attractions", you MAY schedule that named place as a real stop, not \
just as color/context - prefer it over a vague filler like "wander the \
old town markets" whenever the guide names something specific. Still do \
not invent details the guide doesn't state (hours, prices, exact \
address) - use it for the name and whatever concrete color it actually \
gives. If attractions are limited and the guide has no more named \
places either, it's fine to fill remaining slots with a light activity, \
free time, or a general activity like "wander the old town markets" \
without a specific named place. Respond with ONLY the JSON object, no \
other text."""


def _guide_activity_lines(destination_guide: dict | None, max_lines: int = 4) -> list[str]:
    """Pull a handful of short, sentence-length snippets out of the RAG
    passages to use as generic (non-place-name) activity suggestions in
    the rule-based fallback - real local detail beats "Free day -
    explore locally" even when there's no LLM and no attraction data.

    NOTE (21 Aug 2026): this used to take only the first qualifying
    sentence from the first qualifying paragraph of EACH passage, capped
    at one line per passage. That silently broke any time RAG returned
    fewer passages than there were days to schedule (very common - a
    short destination-guide entry retrieves as a single passage): with
    only 1 unique line and `guide_lines[i % len(guide_lines)]` cycling
    it, every single day printed the exact same sentence. Now it walks
    ALL paragraphs of ALL passages, so one meaty passage alone can supply
    a full trip's worth of distinct lines."""
    if not destination_guide:
        return []

    lines: list[str] = []
    seen: set[str] = set()
    for passage in destination_guide.get("passages", []):
        # First sentence of each paragraph tends to be the topic
        # sentence (see chunking.py's paragraph-boundary splitting) -
        # short enough to use as a single activity line, unlike a whole
        # multi-sentence passage.
        for para in passage["content"].split("\n\n"):
            sentence = re.split(r"(?<=[.!?])\s+", para.strip(), maxsplit=1)[0].strip()
            if 20 <= len(sentence) <= 160 and sentence not in seen:
                lines.append(sentence)
                seen.add(sentence)
                if len(lines) >= max_lines:
                    return lines
    return lines


# Fixed daily time slots for the rule-based fallback. The 3 meal slots
# are always generic (no live restaurant data feeds this path); the 3
# "None" slots get filled from real attraction names first, then
# destination-guide lines, then a generic filler - see _fallback_itinerary.
_FALLBACK_SLOTS: list[tuple[str, str | None]] = [
    ("08:00", "Breakfast at the hotel"),
    ("10:00", None),
    ("13:00", "Lunch - try a local specialty"),
    ("15:30", None),
    ("17:30", None),
    ("19:30", "Dinner"),
]


def _fallback_itinerary(
    start_str: str | None,
    end_str: str | None,
    attractions: list[dict],
    destination_guide: dict | None = None,
) -> dict:
    """Deterministic round-robin scheduler used when the LLM is
    unavailable - no creativity, but never fails and never invents data
    that wasn't in `attractions` or the guide passages. Same timed-slot
    shape as the LLM path (see _SYSTEM_PROMPT) so the frontend never has
    to special-case which one produced a given trip."""
    if not start_str or not end_str:
        return {"days": [], "notes": "Insufficient date info to build a schedule."}

    start = date.fromisoformat(start_str)
    end = date.fromisoformat(end_str)
    n_days = max(1, (end - start).days + 1)
    guide_lines = _guide_activity_lines(destination_guide, max_lines=n_days * 3)

    # Round-robin every real attraction name and every guide line across
    # the trip's open ("None") slots, in order, so nothing repeats until
    # the pool is actually exhausted.
    attraction_names = [a["name"] for a in attractions]
    filler_pool = attraction_names + [g for g in guide_lines if g not in attraction_names]
    filler_idx = 0

    days = []
    for i in range(n_days):
        day_date = (start + timedelta(days=i)).isoformat()
        activities = []
        for time_str, label in _FALLBACK_SLOTS:
            if label is not None:
                activities.append({"time": time_str, "activity": label})
                continue
            if filler_idx < len(filler_pool):
                activities.append({"time": time_str, "activity": f"Visit {filler_pool[filler_idx]}"
                                    if filler_idx < len(attraction_names) else filler_pool[filler_idx]})
                filler_idx += 1
            else:
                activities.append({"time": time_str, "activity": "Free time to explore"})
        summary = f"Visit {attraction_names[0]}" if (i == 0 and attraction_names) else f"Day {i + 1}"
        days.append({"date": day_date, "summary": summary, "activities": activities})

    notes = "Generated via rule-based fallback (LLM unavailable)."
    if not attractions and guide_lines:
        notes += " Activities are drawn from destination-guide background reading, not live attraction data."
    return {"days": days, "notes": notes}


class SchedulingAgent:
    async def run(self, state: TripPlanningState) -> dict:
        errors = list(state.get("errors", []))
        start = state.get("start_date")
        end = state.get("end_date")
        attractions = state.get("attractions") or []
        destination_guide = state.get("destination_guide")

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
                "destination_guide": [
                    p["content"] for p in (destination_guide or {}).get("passages", [])[:3]
                ] or None,
            }
            itinerary = await chat_json(_SYSTEM_PROMPT, json.dumps(payload, default=str))
        except Exception as exc:
            errors.append(f"SchedulingAgent: LLM scheduling failed ({exc}), used round-robin fallback")
            itinerary = _fallback_itinerary(start, end, attractions, destination_guide)

        return {"itinerary": itinerary, "errors": errors}
