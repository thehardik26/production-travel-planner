"""
BudgetAgent - deliberately rule-based, NOT an LLM call. Summing numbers
that are already in the state (flight/hotel prices from ResearchAgent)
is a job for plain arithmetic - reaching for an LLM here would add
latency, cost, and a chance of the model just getting the sum wrong,
for zero benefit. Not every agent in a "multi-agent" system needs to be
an LLM call; using one only where the task actually needs language
understanding (IntentAgent, SchedulingAgent) is itself a design
decision worth being able to explain.

NOTE (19 Jul 2026): flights now come from Duffel (migrated off Amadeus,
which decommissioned its self-service portal), and hotels come from
Google Places, which has no live pricing at all. So "estimated_total"
in practice is usually flights-only - the currency label is read from
the actual flight offer data instead of being hardcoded, since Duffel
doesn't always quote in USD the way the old Amadeus mock/test data did.

NOTE (21 Aug 2026): found via review - when tool_currency and the
user's budget_currency actually differ (routine for this India-focused
planner: Duffel commonly quotes USD, budget_currency defaults to INR),
`over_budget` used to compare the two raw numbers directly with no FX
conversion, e.g. "is 600 > 40000" for a $600 USD flight against a
₹40,000 budget - always False regardless of the real (INR-converted)
answer. First fix: report `over_budget = None` (unknown) instead of a
confident, often-wrong True/False when the currencies don't match.

NOTE (21 Aug 2026, second pass): "unknown" was honest but not actually
useful to someone trying to tell if their trip fits their budget - so
`over_budget` now actually converts via app/core/fx.py (free, keyless,
ECB-backed) and compares the converted amount. `over_budget` is still
`None` in the one case that genuinely can't be answered: the FX lookup
itself failing (network blip, frankfurter.app down, unrecognized
currency code) - same graceful-degradation shape as every other
external dependency in this project, just one layer further in than
before. The raw tool-currency total (`estimated_total`) is kept as-is
in the summary so the UI can still show "$45" honestly; the converted
figure is a separate `estimated_total_converted` field so nothing that
already reads `estimated_total` silently starts seeing INR where it
expected USD.
"""
from __future__ import annotations

from app.core.fx import get_fx_rate
from app.orchestration.state import TripPlanningState


class BudgetAgent:
    async def run(self, state: TripPlanningState) -> dict:
        flights = state.get("flights") or []
        hotels = state.get("hotels") or []
        budget = state.get("budget")
        currency = (state.get("budget_currency") or "INR").upper()
        errors = list(state.get("errors", []))

        flight_prices = [f["price"] for f in flights if f.get("price") is not None]
        hotel_prices = [h["price"] for h in hotels if h.get("price") is not None]

        cheapest_flight = min(flight_prices) if flight_prices else None
        cheapest_hotel = min(hotel_prices) if hotel_prices else None

        # currency actually quoted by the tools, not assumed - flights
        # (Duffel) is the more likely source of a real number since
        # hotels (Google Places) never returns a price
        cheapest_flight_entry = next((f for f in flights if f.get("price") == cheapest_flight), None)
        tool_currency = ((cheapest_flight_entry or {}).get("currency") or "USD").upper()

        components = {"flights": cheapest_flight, "hotels": cheapest_hotel}
        known_values = [v for v in components.values() if v is not None]
        estimated_total = sum(known_values) if known_values else None
        missing = [k for k, v in components.items() if v is None]

        currency_mismatch = bool(known_values) and currency != tool_currency
        converted_total = None
        fx_rate = None
        if currency_mismatch:
            fx_rate = await get_fx_rate(tool_currency, currency)
            if fx_rate is not None:
                converted_total = round(estimated_total * fx_rate, 2)
                # NOTE (21 Aug 2026): found via a real user report ("this
                # looks childish") - this branch is the SUCCESS path (the
                # conversion worked), but it used to push a sentence into
                # `errors`, which VerificationAgent/the frontend both
                # treat as "something went wrong" - a working currency
                # conversion doesn't belong in a warning box next to an
                # actual tool failure. The "approximate rate, may vary at
                # booking time" caveat is still communicated - just
                # honestly, as a quiet inline note under the estimate
                # itself (see TripResult.jsx's "≈ ... (approx.)" line),
                # not as an alarm. Only the FAILURE branch below (the
                # conversion couldn't be done at all) is a real problem
                # worth a warning.
                pass
            else:
                errors.append(
                    f"BudgetAgent: tool prices are in {tool_currency} but budget_currency is "
                    f"{currency}, and the currency-conversion lookup failed - over/under-budget "
                    f"can't be determined right now"
                )

        # What we actually compare against the budget: the converted
        # total when currencies differed and conversion succeeded,
        # otherwise the raw estimated_total when currencies already
        # matched. If currencies differ and conversion failed, there's
        # nothing safe to compare - stays None, same as `over_budget`.
        compare_total = converted_total if currency_mismatch else estimated_total

        summary = {
            "estimated_total": estimated_total,
            "estimated_total_currency": tool_currency,
            "estimated_total_converted": converted_total,
            "fx_rate": fx_rate,
            "budget": budget,
            "budget_currency": currency,
            "components": components,
            "missing_estimates": missing,
            "over_budget": (
                None
                if compare_total is None or budget is None
                else compare_total > budget
            ),
        }

        return {"budget_summary": summary, "errors": errors}
