"""
eval/cases.py - the handful of representative trip queries eval/run_eval.py
runs through the real pipeline. Each case is deliberately chosen to
exercise a DIFFERENT known edge case this project has actually hit
during manual testing this cycle (see the dated NOTEs across the agents/
MCP servers this file's queries correspond to) - this is the harness
turning "a user found this bug by hand" into "this stays caught".

Dates are computed relative to today() rather than hardcoded, so this
file doesn't silently rot into testing only past dates.
"""
from __future__ import annotations

from datetime import date, timedelta


def _in_days(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


EVAL_CASES = [
    {
        "name": "goa_full_happy_path",
        "query": (
            f"5 day trip to Goa from Delhi starting {_in_days(10)}, "
            "budget 50000 INR, 2 travelers, love food and beaches"
        ),
        # The "normal" case: real origin, real budget, a destination
        # with RAG coverage and generally good OSM attraction density.
        "expect": {"destination_contains": "goa", "expect_flights": True},
    },
    {
        "name": "pondicherry_rag_grounding",
        "query": (
            f"4 day trip to Pondicherry from Chennai starting {_in_days(12)}, "
            "budget 40000 INR, 2 travelers, love culture and food"
        ),
        # Directly exercises the 21 Aug scheduling_agent.py fix: the
        # itinerary should actually USE at least one real, specific
        # place name from the destination-guide text (Auroville,
        # Promenade Beach, Sri Aurobindo Ashram, the French Quarter/
        # White Town), not just treat the guide as background color.
        "expect": {
            "destination_contains": "pondicherry",
            "expect_flights": True,
            "named_places_any": [
                "Auroville", "Promenade Beach", "Sri Aurobindo Ashram",
                "French Quarter", "White Town", "Matrimandir",
            ],
        },
    },
    {
        "name": "no_origin_city",
        "query": (
            f"3 day trip to Manali starting {_in_days(15)}, "
            "budget 20000 INR, 1 traveler, love mountains and adventure"
        ),
        # No "from <city>" - exercises the 21 Aug verification_agent.py
        # fix: should get the explicit "no departure city" warning, and
        # must NOT get the misleading "check DUFFEL_API_KEY" hint (that
        # warning is only correct when an origin WAS given and flights
        # still failed).
        "expect": {
            "destination_contains": "manali",
            "expect_flights": False,
            "warning_contains": "No departure city was given",
            "warning_not_contains": "DUFFEL_API_KEY",
        },
    },
    {
        "name": "same_day_trip",
        "query": f"1 day trip to Mumbai from Pune on {_in_days(8)}",
        # check_in == check_out - exercises the mcp-hotels-server.py fix
        # for the over-corrected reversed-date validation (should default
        # to 1 night, not reject the request outright).
        "expect": {"destination_contains": "mumbai"},
    },
    {
        "name": "unknown_city_typo",
        "query": (
            f"3 day trip to Xyzzyfalls from Delhi starting {_in_days(9)}, "
            "budget 15000 INR, 1 traveler"
        ),
        # A destination that can't be geocoded anywhere (weather/hotels/
        # attractions/transport will all fail to resolve it) - the point
        # of this case is purely "does the whole request still come back
        # with SOME response instead of a 502", i.e. the graceful-
        # degradation story actually holds under a genuinely bad input.
        "expect": {},
    },
    {
        "name": "no_rag_coverage_destination",
        "query": (
            f"3 day trip to Hampi from Bangalore starting {_in_days(11)}, "
            "budget 15000 INR, 2 travelers, love history"
        ),
        # A real, well-known destination that is NOT one of the 10
        # hand-written knowledge_base.py entries - itinerary should still
        # build fine from OSM attraction data alone, destination_guide
        # should just be empty/None, not an error.
        "expect": {"destination_contains": "hampi"},
    },
    {
        "name": "weather_beyond_forecast_window",
        "query": (
            f"3 day trip to Jaipur from Delhi starting {_in_days(25)}, "
            "budget 30000 INR, 2 travelers, love culture"
        ),
        # Open-Meteo only forecasts ~16 days out - this date is
        # deliberately further than that, so this should surface the
        # (now-cleaned-up, see mcp_clients/base.py's 21 Aug NOTE) "isn't
        # available yet" weather warning rather than crash or silently
        # show no weather at all.
        "expect": {"destination_contains": "jaipur", "warning_contains": "isn't available yet"},
    },
]
