"""
eval/checks.py - pure, network-free functions that score a single
POST /api/trips/plan response (a plain dict, same shape as
TripPlanResponse - see app/api/routes/trips.py). Every function here
takes that dict (plus, for a few, a small expectation) and returns a
CheckResult - it never makes a request, opens a DB connection, or calls
an LLM itself, which is what makes these independently unit-testable
(see tests/test_eval_checks.py) without the full stack running.

DESIGN NOTE: `passed` is a tri-state, not a bool - True/False for an
actual pass/fail, and None for "not applicable to this response" (e.g.
checking budget math when there was no budget at all). eval/run_eval.py
renders None as SKIP, not FAIL - a check that doesn't apply isn't a
failure.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date


@dataclass
class CheckResult:
    name: str
    passed: bool | None  # True/False, or None if not applicable
    detail: str


def _activity_text(activity) -> str:
    """Activities can be a plain string (older trips, or the pre-timed
    fallback shape) or a {time, activity} object (current LLM + fallback
    shape) - see TripResult.jsx's identical handling on the frontend
    side. Same duck-typing here so this file works against either."""
    if isinstance(activity, dict):
        return str(activity.get("activity", ""))
    return str(activity)


def check_destination_parsed(response: dict, expect_substring: str | None = None) -> CheckResult:
    destination = response.get("destination") or ""
    if not destination:
        return CheckResult("destination_parsed", False, "IntentAgent did not parse a destination at all")
    if expect_substring and expect_substring.lower() not in destination.lower():
        return CheckResult(
            "destination_parsed", False,
            f"parsed destination {destination!r} does not contain expected {expect_substring!r}",
        )
    return CheckResult("destination_parsed", True, f"destination={destination!r}")


def check_day_count(response: dict) -> CheckResult:
    start, end = response.get("start_date"), response.get("end_date")
    days = (response.get("itinerary") or {}).get("days") or []
    if not start or not end:
        return CheckResult("day_count", None, "no start/end date on the response to check against")
    try:
        expected = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    except ValueError:
        return CheckResult("day_count", None, f"malformed start/end date ({start!r}, {end!r})")
    ok = len(days) == expected
    return CheckResult("day_count", ok, f"expected {expected} day(s) from the trip dates, itinerary has {len(days)}")


def check_no_empty_days(response: dict) -> CheckResult:
    days = (response.get("itinerary") or {}).get("days") or []
    if not days:
        return CheckResult("no_empty_days", None, "no days in the itinerary to check")
    empty = [d.get("date") for d in days if not d.get("activities")]
    return CheckResult(
        "no_empty_days", len(empty) == 0,
        f"{len(empty)} day(s) with zero activities: {empty}" if empty else "every day has at least one activity",
    )


_MEAL_WORDS = ("breakfast", "lunch", "dinner")


def check_meals_present(response: dict) -> CheckResult:
    """SchedulingAgent's own system prompt (see agents/scheduling_agent.py)
    promises a breakfast/lunch/dinner slot every day, even a generic one
    - this just verifies that promise actually held for this response."""
    days = (response.get("itinerary") or {}).get("days") or []
    if not days:
        return CheckResult("meals_present", None, "no days in the itinerary to check")
    missing = []
    for d in days:
        text = " ".join(_activity_text(a) for a in (d.get("activities") or [])).lower()
        if not any(word in text for word in _MEAL_WORDS):
            missing.append(d.get("date"))
    return CheckResult(
        "meals_present", len(missing) == 0,
        f"{len(missing)} day(s) mention no meal at all: {missing}" if missing else "every day mentions a meal",
    )


def check_budget_math(response: dict) -> CheckResult:
    """Recomputes over_budget from the numbers already in the response
    and checks it against what BudgetAgent actually returned - a cheap
    regression guard against exactly the class of bug this project hit
    twice already (raw-number comparison across mismatched currencies,
    see budget_agent.py's 21 Aug NOTEs)."""
    summary = response.get("budget_summary")
    if not summary or summary.get("budget") is None:
        return CheckResult("budget_math", None, "no budget on this request to check")

    est_currency = summary.get("estimated_total_currency")
    budget_currency = summary.get("budget_currency")
    currencies_differ = bool(est_currency) and bool(budget_currency) and est_currency != budget_currency
    compare_total = summary.get("estimated_total_converted") if currencies_differ else summary.get("estimated_total")

    if compare_total is None:
        # Legitimately unknowable (no prices at all, or currencies
        # differed and the FX lookup itself failed) - BudgetAgent is
        # supposed to report over_budget=None in exactly this case.
        ok = summary.get("over_budget") is None
        return CheckResult(
            "budget_math", ok,
            f"no comparable total available - expected over_budget=None, got {summary.get('over_budget')!r}",
        )

    expected_over = compare_total > summary["budget"]
    ok = summary.get("over_budget") == expected_over
    return CheckResult(
        "budget_math", ok,
        f"compare_total={compare_total} budget={summary['budget']} "
        f"-> expected over_budget={expected_over}, got {summary.get('over_budget')!r}",
    )


def check_warning_contains(response: dict, substring: str) -> CheckResult:
    text = " ".join((response.get("warnings") or []) + (response.get("errors") or []))
    found = substring.lower() in text.lower()
    return CheckResult("warning_contains", found, f"looking for {substring!r} in warnings/errors")


def check_warning_not_contains(response: dict, substring: str) -> CheckResult:
    text = " ".join((response.get("warnings") or []) + (response.get("errors") or []))
    found = substring.lower() in text.lower()
    return CheckResult("warning_not_contains", not found, f"{substring!r} should NOT appear in warnings/errors")


def check_named_places_used(response: dict, candidates: list[str]) -> CheckResult:
    """A cheap POSITIVE groundedness signal for destinations with RAG
    coverage: does the itinerary actually use at least one of a short
    list of real, known place names for this destination (drawn from
    the destination guide or attractions data)? This does NOT prove
    every activity is grounded - see scan_unverified_phrases below for
    the (heuristic, informational-only) attempt at that."""
    days = (response.get("itinerary") or {}).get("days") or []
    text = " ".join(_activity_text(a) for d in days for a in (d.get("activities") or [])).lower()
    hits = [c for c in candidates if c.lower() in text]
    return CheckResult(
        "named_places_used", len(hits) > 0,
        f"found: {hits}" if hits else f"none of {candidates} appeared anywhere in the itinerary",
    )


# --- informational-only heuristic below: never pass/fail, just flagged for a human ---

_GENERIC_PHRASE_WORDS = {
    "breakfast", "lunch", "dinner", "hotel", "free", "time", "explore", "visit",
    "local", "market", "town", "day", "morning", "evening", "afternoon", "wander",
    "relax", "arrival", "departure", "check", "shopping", "restaurant", "walk",
    "sunset", "sunrise", "old", "city", "area", "trip", "pack", "transport",
    "airport", "board", "depart", "arrive", "return", "head", "drive", "stroll",
    "discover", "enjoy", "take", "in",
}
_PROPER_NOUN_RE = re.compile(r"\b[A-Z][a-zA-Z']+(?:\s+[A-Z][a-zA-Z']+)*\b")


def _gazetteer(response: dict) -> str:
    """Every real, known-name string this trip's own data actually
    contains - attraction/transport names plus the raw destination-guide
    text - lowercased into one blob to substring-match candidate phrases
    against."""
    research = response.get("research") or response  # POST /plan and GET /trips/{id} differ slightly - tolerate both
    parts: list[str] = []
    for item in (research.get("attractions") or []):
        if item.get("name"):
            parts.append(item["name"])
    for item in (research.get("transport") or []):
        if item.get("name"):
            parts.append(item["name"])
    guide = research.get("destination_guide") or {}
    for passage in guide.get("passages") or []:
        parts.append(passage.get("content", ""))
        parts.append(passage.get("title", ""))
    return " ".join(parts).lower()


def scan_unverified_phrases(response: dict) -> list[str]:
    """Best-effort, HEURISTIC-ONLY scan: capitalized phrases in itinerary
    activity text that don't appear anywhere in this trip's own
    attractions/transport/destination_guide data - i.e. a *possible*
    hallucinated place name SchedulingAgent's LLM path invented despite
    its system prompt forbidding that (see scheduling_agent.py). This
    WILL have false positives - ordinary capitalized words at the start
    of a sentence, dish names, generic phrases like "Old Town" - it is
    not a verdict, just something worth a human's 5-second glance.
    Deliberately returns a plain list, not a CheckResult - there's no
    honest pass/fail threshold for "how many false-positive-prone
    heuristic flags is too many"."""
    gazetteer = _gazetteer(response)
    days = (response.get("itinerary") or {}).get("days") or []
    seen: set[str] = set()
    flagged: list[str] = []
    for d in days:
        for a in d.get("activities") or []:
            text = _activity_text(a)
            for match in _PROPER_NOUN_RE.findall(text):
                words = match.split()
                # Trim generic leading/trailing words before judging the
                # match. An activity almost always OPENS with a
                # capitalized action verb ("Visit Baga Beach", "Explore
                # the Old Fort") - capitalization alone can't tell that
                # verb apart from a real place name, so without this the
                # scan flagged "Visit Baga Beach" as ungrounded even
                # though "Baga Beach" itself is real and in the
                # gazetteer (caught by this file's own unit tests before
                # ever reaching a real user).
                while words and words[0].lower() in _GENERIC_PHRASE_WORDS:
                    words.pop(0)
                while words and words[-1].lower() in _GENERIC_PHRASE_WORDS:
                    words.pop()
                if not words:
                    continue
                core = " ".join(words)
                key = core.lower()
                if key in seen:
                    continue
                if key in gazetteer:
                    continue
                seen.add(key)
                flagged.append(core)
    return flagged
