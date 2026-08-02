"""
IntentAgent - first node in the graph. Turns the user's free-text
request ("5 din Goa trip, budget 50k, 2 log, food aur beaches pasand
hai") into the structured fields every later agent needs
(origin/destination/dates/budget/travelers/preferences).

This is the one agent where an LLM call is genuinely necessary - parsing
open-ended natural language into a fixed schema is exactly what LLMs are
good at and hand-written regex is bad at. But the LLM is a dependency
that can fail (no key set, Groq down, rate limited) - RESILIENCE means
the whole planning run should not crash just because free-text parsing
failed. _heuristic_parse() is the fallback: much dumber (keyword
matching, sane defaults), but keeps the graph moving instead of dying.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from app.core.llm import chat_json
from app.orchestration.state import TripPlanningState

_SYSTEM_PROMPT_TEMPLATE = """You extract structured trip-planning fields \
from a user's free-text travel request. Today's real-world date is \
{today} - use this, not your own assumption, as "now" when the user's \
request doesn't give an explicit date (e.g. "5 day trip next month" \
means starting roughly 30 days after {today}, not a date from your \
training data). Always respond with a single JSON object with exactly \
these keys:

origin (string or null - departure city),
destination (string - the trip destination city; guess the most likely \
single city if ambiguous),
start_date (string YYYY-MM-DD, must be on or after {today} - estimate a \
reasonable near-future date if not given),
end_date (string YYYY-MM-DD, must be after start_date),
travelers (integer, default 1 if not mentioned),
budget (number or null - total trip budget if mentioned),
budget_currency (string, 3-letter code, default "INR"),
preferences (array of short lowercase strings, e.g. ["food", "culture", \
"adventure", "beaches", "nightlife"] - infer from the text, empty array \
if nothing specific is mentioned).

Respond with ONLY the JSON object, no other text."""


def _heuristic_parse(query: str) -> dict:
    """Dumb fallback used when the LLM is unavailable. Open-Meteo (the
    weather tool) only forecasts ~16 days ahead, so defaults lean near-
    term rather than picking an arbitrary distant date."""
    today = date.today()
    start = today + timedelta(days=5)
    end = start + timedelta(days=4)

    budget_match = re.search(r"(\d{4,7})", query.replace(",", ""))
    travelers_match = re.search(r"(\d+)\s*(people|travelers|persons|log|pax)", query, re.IGNORECASE)

    known_cities = ["goa", "delhi", "mumbai", "bangalore", "bengaluru", "chennai",
                     "kolkata", "hyderabad", "paris", "london", "dubai", "tokyo",
                     "singapore", "bangkok", "bali", "new york"]
    lowered = query.lower()
    destination = next((c.title() for c in known_cities if c in lowered), "Goa")

    return {
        "origin": None,
        "destination": destination,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "travelers": int(travelers_match.group(1)) if travelers_match else 1,
        "budget": float(budget_match.group(1)) if budget_match else None,
        "budget_currency": "INR",
        "preferences": [],
    }


class IntentAgent:
    async def run(self, state: TripPlanningState) -> dict:
        query = state["user_query"]
        errors = list(state.get("errors", []))

        try:
            today = date.today().isoformat()
            system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(today=today)
            parsed = await chat_json(system_prompt, query)
        except Exception as exc:
            errors.append(f"IntentAgent: LLM parse failed ({exc}), used heuristic fallback")
            parsed = _heuristic_parse(query)

        return {
            "origin": parsed.get("origin"),
            "destination": parsed.get("destination"),
            "start_date": parsed.get("start_date"),
            "end_date": parsed.get("end_date"),
            "travelers": parsed.get("travelers", 1),
            "budget": parsed.get("budget"),
            "budget_currency": parsed.get("budget_currency", "INR"),
            "preferences": parsed.get("preferences", []),
            "errors": errors,
        }
