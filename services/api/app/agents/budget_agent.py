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
"""
from __future__ import annotations

from app.orchestration.state import TripPlanningState


class BudgetAgent:
    async def run(self, state: TripPlanningState) -> dict:
        flights = state.get("flights") or []
        hotels = state.get("hotels") or []
        budget = state.get("budget")
        currency = state.get("budget_currency") or "INR"
        errors = list(state.get("errors", []))

        flight_prices = [f["price"] for f in flights if f.get("price") is not None]
        hotel_prices = [h["price"] for h in hotels if h.get("price") is not None]

        cheapest_flight = min(flight_prices) if flight_prices else None
        cheapest_hotel = min(hotel_prices) if hotel_prices else None

        # currency actually quoted by the tools, not assumed - flights
        # (Duffel) is the more likely source of a real number since
        # hotels (Google Places) never returns a price
        cheapest_flight_entry = next((f for f in flights if f.get("price") == cheapest_flight), None)
        tool_currency = (cheapest_flight_entry or {}).get("currency") or "USD"

        components = {"flights": cheapest_flight, "hotels": cheapest_hotel}
        known_values = [v for v in components.values() if v is not None]
        estimated_total = sum(known_values) if known_values else None
        missing = [k for k, v in components.items() if v is None]

        if known_values and currency != tool_currency:
            errors.append(
                f"BudgetAgent: tool prices are in {tool_currency} but budget_currency is "
                f"{currency} - comparison below is approximate (no FX conversion applied)"
            )

        summary = {
            "estimated_total": estimated_total,
            "estimated_total_currency": tool_currency,
            "budget": budget,
            "budget_currency": currency,
            "components": components,
            "missing_estimates": missing,
            "over_budget": (
                estimated_total is not None and budget is not None and estimated_total > budget
            ),
        }

        return {"budget_summary": summary, "errors": errors}
