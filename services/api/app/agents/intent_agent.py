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
{today}, a {today_weekday} - use this, not your own assumption, as "now" \
when the user's request doesn't give an explicit date (e.g. "5 day trip \
next month" means starting roughly 30 days after {today}, not a date \
from your training data). Always respond with a single JSON object with \
exactly these keys:

origin (string or null - departure city),
destination (string - the trip destination city; guess the most likely \
single city if ambiguous),
start_date (string YYYY-MM-DD, must be on or after {today} - estimate a \
reasonable near-future date if not given. IMPORTANT for relative terms: \
a "weekend"/"this weekend" trip always starts on a Saturday and ends on \
a Sunday, never a weekday. If {today} ({today_weekday}) IS a Saturday, \
that Saturday is today. Otherwise use the NEXT calendar Saturday after \
{today} - including when {today} is a Sunday, since that Saturday has \
already passed and start_date can never be before {today}. "next \
weekend" means the Saturday after THAT one. Compute the actual calendar \
date from {today} being a {today_weekday}, don't guess.),
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
    term rather than picking an arbitrary distant date.

    NOTE (21 Aug 2026): two bugs fixed here after this fallback got
    exercised for real (Groq unreachable from a sandboxed environment)
    and produced a request that should have succeeded but didn't:

    1. The old budget regex (`\\d{4,7}` anywhere in the query) happily
       matched the "2026" in a "starting 2026-08-05" date before it ever
       reached the actual "budget 15000" further along the string - the
       budget gate then rejected a perfectly good request as
       impossibly cheap. Now we look for a number tagged with a
       currency/"budget" cue first, and only fall back to a bare
       digit-run (with YYYY-MM-DD dates stripped out first) if nothing
       tagged is found.
    2. `next(c for c in known_cities if c in lowered)` picked whichever
       known city happened to appear FIRST in the string, so "trip to
       Lonavala from Mumbai" (a city not in the list) fell back to
       matching "mumbai" - the ORIGIN - as the destination. Now "to X"
       / "from Y" phrasing is parsed explicitly so origin and
       destination aren't just guessed from word order.
    3. "Weekend trip" always fell through to the generic today+5-days
       default (a Wednesday, if today's a Friday - not a weekend at
       all), because nothing here looked at the word "weekend". Now it's
       detected explicitly and mapped to the next actual Saturday/Sunday.
    """
    today = date.today()
    if re.search(r"\bweekend\b", query, re.IGNORECASE):
        # Monday=0 ... Saturday=5, Sunday=6. (5 - weekday) % 7 gives days
        # until the next Saturday - 0 if today already IS Saturday.
        #
        # NOTE (21 Aug 2026, second pass): the first version of this
        # comment claimed Sunday ALSO resolves to "0 days ahead / today",
        # matching the phrase "this weekend" - that was wrong and never
        # matched the actual arithmetic below. On a Sunday, (5-6)%7 = 6,
        # i.e. NEXT Saturday, not today. That's the behavior being kept
        # (not "fixed to 0"): start_date can never be before {today} (see
        # the LLM prompt above), and this weekend's Saturday has already
        # passed by Sunday, so jumping to next week's Saturday is the
        # only option that's both in the future and an actual Sat-Sun
        # pair - not "today only" (a 1-day trip nobody asked for).
        days_to_saturday = (5 - today.weekday()) % 7
        start = today + timedelta(days=days_to_saturday)
        end = start + timedelta(days=1)
    else:
        start = today + timedelta(days=5)
        end = start + timedelta(days=4)

    currency_budget_match = re.search(
        r"(?:budget\s*(?:of|is)?\s*(?:rs\.?|inr|₹)?\s*|(?:rs\.?|inr|₹)\s*)([\d,]{3,9})",
        query,
        re.IGNORECASE,
    )
    if currency_budget_match:
        budget_value = float(currency_budget_match.group(1).replace(",", ""))
    else:
        # Last resort: any 4-7 digit run, but with YYYY-MM-DD dates
        # stripped first so a start/end date is never mistaken for a
        # budget figure.
        no_dates = re.sub(r"\d{4}-\d{2}-\d{2}", "", query)
        bare_match = re.search(r"(\d{4,7})", no_dates.replace(",", ""))
        budget_value = float(bare_match.group(1)) if bare_match else None

    travelers_match = re.search(r"(\d+)\s*(people|travelers|persons|log|pax)", query, re.IGNORECASE)

    known_cities = ["goa", "delhi", "mumbai", "bangalore", "bengaluru", "chennai",
                     "kolkata", "hyderabad", "pune", "jaipur", "udaipur", "agra",
                     "lonavala", "manali", "shimla", "ooty", "munnar", "kerala",
                     "darjeeling", "rishikesh", "pondicherry", "paris", "london",
                     "dubai", "tokyo", "singapore", "bangkok", "bali", "new york"]

    def _known_city_in(text: str | None) -> str | None:
        if not text:
            return None
        t = text.lower()
        return next((c.title() for c in known_cities if c in t), None)

    to_match = re.search(r"\bto\s+([A-Za-z][A-Za-z\s]{2,24}?)(?=\s+from\b|[,.]|$)", query, re.IGNORECASE)
    from_match = re.search(
        r"\bfrom\s+([A-Za-z][A-Za-z\s]{2,24}?)(?=\s+(?:to|starting|budget|on|for)\b|[,.]|$)",
        query,
        re.IGNORECASE,
    )

    origin = _known_city_in(from_match.group(1) if from_match else None)
    destination = _known_city_in(to_match.group(1) if to_match else None)

    if not destination:
        lowered = query.lower()
        # Fall back to "first known city in the query that isn't the
        # origin we already found" rather than picking blindly.
        destination = next(
            (c.title() for c in known_cities if c in lowered and c != (origin or "").lower()),
            "Goa",
        )

    return {
        "origin": origin,
        "destination": destination,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "travelers": int(travelers_match.group(1)) if travelers_match else 1,
        "budget": budget_value,
        "budget_currency": "INR",
        "preferences": [],
    }


class IntentAgent:
    async def run(self, state: TripPlanningState) -> dict:
        query = state["user_query"]
        errors = list(state.get("errors", []))

        try:
            today_date = date.today()
            system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
                today=today_date.isoformat(),
                today_weekday=today_date.strftime("%A"),
            )
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
