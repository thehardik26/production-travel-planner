"""
eval/run_eval.py - runs eval/cases.py's queries through the REAL,
currently-running /api/trips/plan endpoint (same "hit the actual dev
stack" philosophy as tests/test_trip_plan_smoke.py - see that file's own
NOTE for why: mocking the LLM/tool calls out would test something other
than the real app) and scores each response with eval/checks.py.

WHAT THIS IS: a small, deterministic, heuristic-based quality smoke test
across a handful of representative trips. It checks structural/logical
properties - right day count, a meal mentioned every day, budget math
internally consistent, the expected warning shows up (or doesn't), and
for RAG-covered destinations, that the itinerary actually uses at least
one real named place from the guide instead of just generic filler.

WHAT THIS IS NOT: a judgment of itinerary QUALITY in any deep "is this
actually a good trip" sense - that would need either a human reviewer or
an LLM-as-judge pass, which this deliberately doesn't do (extra cost,
extra latency, and LLM judges have their own accuracy problems). It's
also not a hallucination detector with any real guarantee - see
checks.scan_unverified_phrases's own docstring for why that part is
informational-only, not pass/fail.

REQUIRES the full local stack running: Postgres, Redis, all 5 MCP tool
servers, and the API itself - exactly what start-everything.ps1/.bat
starts. From services/api, with the venv active:

    python -m eval.run_eval

Point it at a different host with EVAL_API_BASE_URL if needed. Each run
signs up a fresh, uniquely-emailed throwaway user (same pattern as
tests/conftest.py's auth_headers fixture) so re-running never collides
with a previous run, and writes a timestamped report to eval/report.md
alongside printing a live summary as it goes.
"""
from __future__ import annotations

import asyncio
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

from eval import checks as ck
from eval.cases import EVAL_CASES

API_BASE_URL = os.environ.get("EVAL_API_BASE_URL", "http://localhost:8000")
REPORT_PATH = Path(__file__).parent / "report.md"
REQUEST_TIMEOUT_SECONDS = 90  # trip planning fans out 5 tool calls + an LLM call - give it real room


async def _get_auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    email = f"eval-{uuid.uuid4().hex[:12]}@example.com"
    password = "eval-harness-password-123"
    signup = await client.post("/api/auth/signup", json={"email": email, "password": password})
    signup.raise_for_status()
    login = await client.post("/api/auth/login", json={"email": email, "password": password})
    login.raise_for_status()
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _score_response(response: dict, expect: dict) -> tuple[list[ck.CheckResult], list[str]]:
    results = [
        ck.check_destination_parsed(response, expect.get("destination_contains")),
        ck.check_day_count(response),
        ck.check_no_empty_days(response),
        ck.check_meals_present(response),
        ck.check_budget_math(response),
    ]
    if "expect_flights" in expect:
        flights = (response.get("research") or {}).get("flights") or []
        got = bool(flights)
        results.append(ck.CheckResult(
            "flights_presence", got == expect["expect_flights"],
            f"expect_flights={expect['expect_flights']}, got {len(flights)} flight(s)",
        ))
    if expect.get("warning_contains"):
        results.append(ck.check_warning_contains(response, expect["warning_contains"]))
    if expect.get("warning_not_contains"):
        results.append(ck.check_warning_not_contains(response, expect["warning_not_contains"]))
    if expect.get("named_places_any"):
        results.append(ck.check_named_places_used(response, expect["named_places_any"]))
    unverified = ck.scan_unverified_phrases(response)
    return results, unverified


async def _run_case(client: httpx.AsyncClient, headers: dict, case: dict) -> dict:
    t0 = time.monotonic()
    try:
        resp = await client.post(
            "/api/trips/plan", json={"query": case["query"]}, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        return {"name": case["name"], "crashed": True, "detail": f"request failed: {exc!r}", "elapsed": time.monotonic() - t0}
    elapsed = time.monotonic() - t0

    if resp.status_code != 200:
        return {
            "name": case["name"], "crashed": True,
            "detail": f"HTTP {resp.status_code}: {resp.text[:300]}", "elapsed": elapsed,
        }

    response = resp.json()
    checks, unverified = _score_response(response, case.get("expect", {}))
    return {
        "name": case["name"],
        "crashed": False,
        "elapsed": elapsed,
        "checks": checks,
        "unverified_phrases": unverified,
        "warnings": response.get("warnings", []),
        "errors": response.get("errors", []),
    }


def _print_case(result: dict) -> None:
    print(f"\n=== {result['name']} ({result['elapsed']:.1f}s) ===")
    if result["crashed"]:
        print(f"  CRASHED: {result['detail']}")
        return
    for c in result["checks"]:
        mark = "SKIP" if c.passed is None else ("PASS" if c.passed else "FAIL")
        print(f"  [{mark}] {c.name}: {c.detail}")
    if result["unverified_phrases"]:
        print(f"  [info] possibly-ungrounded phrases (heuristic - review, don't assume): {result['unverified_phrases']}")


def _write_report(case_results: list[dict]) -> None:
    total = passed = crashed = 0
    lines = [f"# Eval report — {datetime.now(timezone.utc).isoformat(timespec='seconds')}Z", ""]
    for result in case_results:
        lines.append(f"## {result['name']}")
        if result["crashed"]:
            crashed += 1
            lines.append(f"- **CRASHED**: {result['detail']}")
            lines.append("")
            continue
        lines.append(f"- elapsed: {result['elapsed']:.1f}s")
        for c in result["checks"]:
            if c.passed is None:
                lines.append(f"- [SKIP] **{c.name}**: {c.detail}")
            else:
                total += 1
                passed += 1 if c.passed else 0
                lines.append(f"- [{'PASS' if c.passed else 'FAIL'}] **{c.name}**: {c.detail}")
        if result["unverified_phrases"]:
            lines.append(f"- [info] possibly-ungrounded phrases (heuristic): {result['unverified_phrases']}")
        if result["warnings"] or result["errors"]:
            lines.append(f"- warnings/errors: {result['warnings'] + result['errors']}")
        lines.append("")

    summary = f"**{passed}/{total} checks passed** across {len(case_results)} case(s)"
    if crashed:
        summary += f" — {crashed} case(s) CRASHED outright (see above)"
    lines.insert(1, summary + "\n")
    REPORT_PATH.write_text("\n".join(lines))


async def main() -> None:
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        try:
            headers = await _get_auth_headers(client)
        except httpx.HTTPError as exc:
            print(f"Could not reach {API_BASE_URL} to sign up an eval user: {exc!r}")
            print("Is the API running (uvicorn app.main:app) and all 5 MCP tool servers up?")
            return

        case_results = []
        for case in EVAL_CASES:
            print(f"Running: {case['name']} ...")
            result = await _run_case(client, headers, case)
            case_results.append(result)
            _print_case(result)

    _write_report(case_results)
    print(f"\nFull report written to {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
