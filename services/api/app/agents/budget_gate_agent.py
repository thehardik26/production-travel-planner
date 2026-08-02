"""
BudgetGateAgent - a cheap, deterministic sanity check that runs right
after IntentAgent and BEFORE ResearchAgent (5 real network calls to
external APIs) or SchedulingAgent (a second Groq LLM call).

WHY THIS EXISTS: without it, a request like "Goa trip, budget INR 1000,
7 days, 2 travelers" still burns every tool call and both LLM calls,
only to report at the very end that no price could possibly fit. That's
wasted latency, wasted upstream-API quota (several of our tools sit on
rate-limited free tiers), and wasted LLM tokens - for a request that
could never have succeeded. Failing fast here is the same principle as
validating a request at any API boundary: reject what you can prove is
invalid cheaply, before paying for anything expensive. This is exactly
the kind of design decision worth being able to explain in an
interview - not every check needs to happen "at the end".

THIS IS A HEURISTIC, NOT A LIVE PRICE FEED: MIN_BUDGET_PER_DAY_PER_TRAVELER_INR
is a deliberately conservative, hardcoded floor for a bare-bones
domestic Indian trip (hostel-level stay + basic food + local transport;
does NOT assume flights). It exists to catch budgets that are an order
of magnitude too low, not to second-guess a legitimately tight but
possible budget - REJECT_BELOW_FRACTION_OF_FLOOR (0.5) deliberately
sets the reject line at HALF the already-conservative floor, so this
only fires on requests that are unambiguously impossible, minimizing
false-positive rejections of real budget travelers.

Only INR budgets are gated (no floor is defined for other currencies)
and only when start/end dates are present - anything else passes
through unchecked rather than guessing.
"""
from __future__ import annotations

from datetime import date

from app.orchestration.state import TripPlanningState

MIN_BUDGET_PER_DAY_PER_TRAVELER_INR = 1500
REJECT_BELOW_FRACTION_OF_FLOOR = 0.5


class BudgetGateAgent:
    async def run(self, state: TripPlanningState) -> dict:
        budget = state.get("budget")
        currency = (state.get("budget_currency") or "INR").upper()
        start = state.get("start_date")
        end = state.get("end_date")
        travelers = state.get("travelers") or 1

        if budget is None or currency != "INR" or not start or not end:
            return {"budget_rejected": False}

        try:
            days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
        except ValueError:
            return {"budget_rejected": False}

        if days <= 0:
            return {"budget_rejected": False}

        floor = MIN_BUDGET_PER_DAY_PER_TRAVELER_INR * days * travelers
        reject_threshold = floor * REJECT_BELOW_FRACTION_OF_FLOOR

        if budget < reject_threshold:
            warnings = list(state.get("warnings", []))
            warnings.append(
                f"Budget of Rs {budget:,.0f} for {days} day(s) and {travelers} "
                f"traveler(s) is far below what's realistically possible - even a "
                f"bare-bones budget trip typically runs Rs {floor:,.0f}+ for this "
                f"duration. Increase the budget or shorten the trip and try again. "
                f"No flights, hotels, attractions or itinerary were searched for "
                f"this request."
            )
            return {"budget_rejected": True, "warnings": warnings}

        return {"budget_rejected": False}
