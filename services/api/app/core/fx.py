"""
Free, keyless currency conversion via Frankfurter (backed by European
Central Bank reference rates - no signup, no API key, no rate limit
tighter than "be reasonable").

NOTE (21 Aug 2026, found live on a real deployment): Frankfurter's old
domain (api.frankfurter.app, no version prefix) now returns a 301
redirect to api.frankfurter.dev/v1/... - a real, permanent API migration
by the project's maintainers, not a transient issue. httpx does NOT
follow redirects by default, so hitting the old URL raised
"Redirect response '301 Moved Permanently'" instead of ever reaching the
actual data - which this file's own except block correctly caught and
degraded to "conversion unavailable" (exactly as designed for a broken
upstream), but the ROOT problem was simply pointing at a dead URL.
settings.FX_API_URL now defaults to the new api.frankfurter.dev/v1
domain directly (same `from`/`to` query params - confirmed via the
redirect's own Location header, which preserved them unchanged), and
`follow_redirects=True` is set below as a second line of defense in
case of another future redirect-based migration.

WHY THIS EXISTS (21 Aug 2026): BudgetAgent compares a tool-quoted price
(Duffel flights, usually USD) against the user's own budget (usually
INR for this India-focused planner). The two used to be compared as raw
numbers with no conversion at all, which produced a confidently WRONG
over/under-budget answer whenever they genuinely differed (see
app/agents/budget_agent.py's NOTE). The fix at the time was to report
"unknown" instead of a wrong answer - honest, but not actually useful to
someone trying to tell if their trip fits their budget. This module
lets BudgetAgent go one step further: convert and actually answer,
while being upfront that it's an approximate market rate, not what
you'd get at time of booking.

RESILIENCE: same story as every other external dependency in this
project (see this file's docstring pattern in mcp_clients/base.py) - a
network blip, an unknown currency code, or frankfurter.app being down
should degrade to "conversion unavailable" (returns None), not crash
the planning run. BudgetAgent already knows how to fall back to
`over_budget = None` with an explanatory warning when this returns
None - that fallback path predates this file and still works exactly
as before if the lookup fails.

NOT routed through the MCP tool-server pattern used for weather/flights/
hotels/attractions/transport: those are tools an LLM agent might decide
to call with varying arguments. This is a plain, deterministic lookup
BudgetAgent always needs when currencies differ - no LLM decision
involved - so a direct cached HTTP call here is simpler than standing up
a 6th MCP server for one GET endpoint.
"""
from __future__ import annotations

import json
import logging

import httpx

from app.core.config import settings
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 8


async def get_fx_rate(from_currency: str, to_currency: str) -> float | None:
    """1 unit of from_currency -> how many units of to_currency.
    Returns None (never raises) if the rate can't be determined for any
    reason - callers decide what "unknown" means for their own display/
    logic, same as every other tool-failure path in this project."""
    from_currency = from_currency.strip().upper()
    to_currency = to_currency.strip().upper()
    if from_currency == to_currency:
        return 1.0

    cache_key = f"fx:{from_currency}:{to_currency}"
    cached = await redis_client.get(cache_key)
    if cached is not None:
        return json.loads(cached)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, follow_redirects=True) as client:
            resp = await client.get(
                settings.FX_API_URL,
                params={"from": from_currency, "to": to_currency},
            )
            resp.raise_for_status()
            rate = resp.json()["rates"][to_currency]
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
        # KeyError/ValueError/TypeError cover a malformed response body
        # or an unrecognized currency code (frankfurter.app returns a
        # 200 with no matching key in "rates" for some inputs rather
        # than a clean 4xx) - all of these mean "can't convert", not
        # "crash the request", so the CALLER still just sees None.
        #
        # NOTE (21 Aug 2026): this used to swallow `exc` completely -
        # BudgetAgent's warning told the user "the lookup failed" but
        # nothing anywhere recorded WHY, so a real failure (firewall/
        # antivirus blocking this specific new domain, frankfurter.app
        # itself briefly down, a changed response shape) was impossible
        # to diagnose after the fact. This logs the real exception to
        # the backend's own console - visible in the terminal window
        # running the API - without changing what the caller sees.
        logger.warning("FX lookup failed for %s->%s: %r", from_currency, to_currency, exc)
        return None

    await redis_client.set(cache_key, json.dumps(rate), ex=settings.FX_CACHE_TTL_SECONDS)
    return float(rate)
