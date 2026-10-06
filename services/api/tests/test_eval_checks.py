"""
Unit tests for eval/checks.py - pure functions, no network/DB/LLM
needed, so unlike tests/test_trip_plan_smoke.py these run standalone
without the full local stack. The point isn't to test the trip-planning
pipeline here (the smoke test already does that) - it's to verify the
eval harness's own scoring logic actually distinguishes a good response
from a broken one, on both sides, for every check it makes. A checker
that always says PASS is worse than no checker at all.
"""
from __future__ import annotations

from eval import checks as ck


def _base_response(**overrides) -> dict:
    """A minimal, well-formed 3-day trip response - the baseline every
    test below starts from and mutates one thing at a time."""
    response = {
        "destination": "Goa",
        "start_date": "2026-09-10",
        "end_date": "2026-09-12",
        "budget_summary": {
            "estimated_total": 150.0,
            "estimated_total_currency": "USD",
            "estimated_total_converted": 14355.0,
            "budget": 50000,
            "budget_currency": "INR",
            "over_budget": False,
        },
        "itinerary": {
            "days": [
                {
                    "date": "2026-09-10",
                    "activities": [
                        {"time": "08:00", "activity": "Breakfast at the hotel"},
                        {"time": "10:00", "activity": "Visit Baga Beach"},
                        {"time": "13:00", "activity": "Lunch at a local eatery"},
                        {"time": "19:30", "activity": "Dinner at a beachfront restaurant"},
                    ],
                },
                {
                    "date": "2026-09-11",
                    "activities": [
                        {"time": "08:00", "activity": "Breakfast at the hotel"},
                        {"time": "10:00", "activity": "Visit Basilica of Bom Jesus"},
                        {"time": "13:00", "activity": "Lunch at a cafe"},
                        {"time": "19:30", "activity": "Dinner at a local restaurant"},
                    ],
                },
                {
                    "date": "2026-09-12",
                    "activities": [
                        {"time": "08:00", "activity": "Breakfast at the hotel"},
                        {"time": "12:00", "activity": "Pack and check out"},
                        {"time": "15:00", "activity": "Transport to the airport"},
                    ],
                },
            ],
        },
        "warnings": [],
        "errors": [],
        "research": {
            "attractions": [{"name": "Baga Beach"}, {"name": "Basilica of Bom Jesus"}],
            "transport": [],
            "destination_guide": {
                "passages": [{"title": "Goa Travel Guide", "content": "Baga Beach and the Basilica of Bom Jesus are must-visits."}]
            },
        },
    }
    response.update(overrides)
    return response


def test_destination_parsed_passes_on_match():
    result = ck.check_destination_parsed(_base_response(), expect_substring="goa")
    assert result.passed is True


def test_destination_parsed_fails_on_mismatch():
    result = ck.check_destination_parsed(_base_response(), expect_substring="manali")
    assert result.passed is False


def test_destination_parsed_fails_when_empty():
    result = ck.check_destination_parsed(_base_response(destination=None))
    assert result.passed is False


def test_day_count_passes_when_matching():
    result = ck.check_day_count(_base_response())
    assert result.passed is True


def test_day_count_fails_when_short_a_day():
    response = _base_response()
    response["itinerary"]["days"] = response["itinerary"]["days"][:2]  # trip spans 3 days, only give 2
    result = ck.check_day_count(response)
    assert result.passed is False


def test_day_count_skips_without_dates():
    result = ck.check_day_count(_base_response(start_date=None))
    assert result.passed is None


def test_no_empty_days_passes():
    assert ck.check_no_empty_days(_base_response()).passed is True


def test_no_empty_days_fails_when_a_day_has_nothing():
    response = _base_response()
    response["itinerary"]["days"][1]["activities"] = []
    result = ck.check_no_empty_days(response)
    assert result.passed is False


def test_meals_present_passes():
    assert ck.check_meals_present(_base_response()).passed is True


def test_meals_present_fails_when_a_day_has_no_meal_at_all():
    response = _base_response()
    response["itinerary"]["days"][0]["activities"] = [{"time": "10:00", "activity": "Visit Baga Beach"}]
    result = ck.check_meals_present(response)
    assert result.passed is False


def test_budget_math_passes_when_consistent():
    assert ck.check_budget_math(_base_response()).passed is True


def test_budget_math_fails_when_over_budget_is_wrong():
    response = _base_response()
    # compare_total (14355 INR) is well under the 50000 budget - claiming
    # over_budget=True here is exactly the class of bug this check exists to catch.
    response["budget_summary"]["over_budget"] = True
    result = ck.check_budget_math(response)
    assert result.passed is False


def test_budget_math_passes_when_none_is_correctly_unknown():
    response = _base_response()
    response["budget_summary"]["estimated_total_converted"] = None  # FX lookup failed
    response["budget_summary"]["over_budget"] = None
    result = ck.check_budget_math(response)
    assert result.passed is True


def test_budget_math_skips_without_a_budget():
    response = _base_response()
    response["budget_summary"]["budget"] = None
    assert ck.check_budget_math(response).passed is None


def test_warning_contains_passes_when_present():
    response = _base_response(warnings=["No departure city was given, so flight search was skipped"])
    result = ck.check_warning_contains(response, "No departure city was given")
    assert result.passed is True


def test_warning_contains_fails_when_absent():
    result = ck.check_warning_contains(_base_response(), "No departure city was given")
    assert result.passed is False


def test_warning_not_contains_fails_when_the_misleading_hint_is_present():
    response = _base_response(warnings=["No flight options found - check mcp-flights-server's DUFFEL_API_KEY"])
    result = ck.check_warning_not_contains(response, "DUFFEL_API_KEY")
    assert result.passed is False


def test_warning_not_contains_passes_when_absent():
    result = ck.check_warning_not_contains(_base_response(), "DUFFEL_API_KEY")
    assert result.passed is True


def test_named_places_used_passes_when_a_guide_place_is_used():
    result = ck.check_named_places_used(_base_response(), ["Baga Beach", "Fontainhas"])
    assert result.passed is True


def test_named_places_used_fails_when_none_are_used():
    result = ck.check_named_places_used(_base_response(), ["Fontainhas", "Chapora Fort"])
    assert result.passed is False


def test_scan_unverified_phrases_is_quiet_on_a_well_grounded_itinerary():
    # Every named place in the baseline fixture (Baga Beach, Basilica of
    # Bom Jesus) is present in research.attractions/destination_guide -
    # a well-behaved response should flag nothing.
    assert ck.scan_unverified_phrases(_base_response()) == []


def test_scan_unverified_phrases_flags_a_place_name_from_nowhere():
    response = _base_response()
    response["itinerary"]["days"][0]["activities"].append(
        {"time": "16:00", "activity": "Visit the Grand Neptune Lighthouse"}
    )
    flagged = ck.scan_unverified_phrases(response)
    assert any("Neptune" in phrase or "Lighthouse" in phrase for phrase in flagged)


def test_scan_unverified_phrases_does_not_flag_generic_filler():
    response = _base_response()
    response["itinerary"]["days"][0]["activities"].append(
        {"time": "16:00", "activity": "Free time to explore the local market"}
    )
    # "Free", "Time", "Market" etc are all in the generic-word list - this
    # shouldn't add any new flags beyond the baseline's empty result.
    assert ck.scan_unverified_phrases(response) == []
