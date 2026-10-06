"""
VerificationAgent - last node before the graph ends. Rule-based, like
BudgetAgent: sanity-checking the itinerary against the request (right
number of days, within budget, no empty days, tools that returned
nothing) is a set of cheap deterministic checks, not something that
benefits from another LLM call. This is the guardrail step - it never
blocks the response, it just surfaces problems into state["warnings"]
so the caller (and eventually the end user) sees them instead of
silently getting a broken or incomplete itinerary.
"""
from __future__ import annotations

from datetime import date

from app.orchestration.state import TripPlanningState


class VerificationAgent:
    async def run(self, state: TripPlanningState) -> dict:
        warnings = list(state.get("warnings", []))
        itinerary = state.get("itinerary") or {}
        budget_summary = state.get("budget_summary") or {}
        start = state.get("start_date")
        end = state.get("end_date")
        days = itinerary.get("days", [])

        if start and end:
            try:
                expected_days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
                if len(days) != expected_days:
                    warnings.append(
                        f"Itinerary has {len(days)} day(s) but the requested dates span {expected_days} day(s)"
                    )
            except ValueError:
                warnings.append("Could not verify itinerary day count - malformed start/end date")

        if budget_summary.get("over_budget"):
            warnings.append(
                f"Estimated cost (~{budget_summary.get('estimated_total')} "
                f"{budget_summary.get('estimated_total_currency')}) exceeds the stated budget "
                f"({budget_summary.get('budget')} {budget_summary.get('budget_currency')})"
            )

        # NOTE (21 Aug 2026): found via review - ResearchAgent (see its
        # own file) silently skips flight search entirely when no origin
        # city was given, since there's nothing to search flights FROM.
        # That's the right call - it's not a failure - but it used to be
        # invisible: no flights shown, no budget estimate possible (see
        # budget_agent.py), and no explanation anywhere for why. This
        # distinguishes "we didn't even try" (tell the user how to get
        # flights next time) from "we tried and it genuinely failed"
        # (the DUFFEL_API_KEY hint below, which is actively MISLEADING
        # advice when the real reason is simply a missing origin).
        if not state.get("origin"):
            warnings.append(
                "No departure city was given, so flight search (and the budget "
                'estimate that depends on it) was skipped - mention where you\'re '
                'traveling FROM (e.g. "...from Mumbai") to see flight options and '
                "an estimated cost."
            )
        elif not state.get("flights"):
            warnings.append("No flight options found - check mcp-flights-server's DUFFEL_API_KEY, or try a different date")
        if not state.get("hotels"):
            warnings.append("No hotel options found - check mcp-hotels-server's GOOGLE_PLACES_API_KEY, or try a different city")
        if not state.get("attractions"):
            warnings.append("No attractions found for this destination")

        for day in days:
            if not day.get("activities"):
                warnings.append(f"Day {day.get('date')} has no planned activities")

        return {"warnings": warnings}
