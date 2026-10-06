# Eval harness

A small, deterministic quality check across a handful of representative
trip-planning queries, run against your actually-running dev stack.

## What this checks

- The right number of days got scheduled for the requested dates
- No day comes back with zero activities
- Every day mentions a meal (breakfast/lunch/dinner) - SchedulingAgent's
  own system prompt promises this
- Budget math is internally consistent (recomputes `over_budget` from
  the numbers in the response and checks it matches)
- Specific warnings show up (or don't) for known edge cases - e.g. "no
  origin city" should get its own clear warning, never the misleading
  "check DUFFEL_API_KEY" one
- For destinations with real destination-guide (RAG) coverage, that the
  itinerary actually uses at least one real named place from the guide,
  not just generic filler - a direct check on the 21 Aug 2026
  scheduling_agent.py fix
- A heuristic, **informational-only** scan for capitalized phrases in
  the itinerary that don't match any real place name this trip's own
  data actually contains (a possible hallucination) - flagged for a
  human to glance at, never auto-failed, because this kind of text
  heuristic has real false positives

## What this does NOT do

- Judge itinerary **quality** in any "is this actually a good trip"
  sense - that needs a human reviewer or an LLM-as-judge pass, neither
  of which this does (cost, latency, and LLM judges have their own
  accuracy problems worth thinking about before adding one)
- Guarantee zero hallucinated place names - the scan above is a
  best-effort heuristic, not a verdict
- Replace tests/test_trip_plan_smoke.py's pytest suite - that suite
  checks the API's plumbing (auth, 404s, one full flow); this checks
  the planning pipeline's output across several different real-world
  edge cases at once

## Running it

Needs the full local stack up: Postgres, Redis, all 5 MCP tool servers,
and the API itself - exactly what `start-everything.ps1`/`.bat` starts.
From `services/api`, with the venv active:

```
python -m eval.run_eval
```

Point it at a different host with `EVAL_API_BASE_URL` (defaults to
`http://localhost:8000`). Each run signs up a fresh throwaway user, so
re-running never collides with a previous run. Prints a live summary as
it goes and writes a full timestamped report to `eval/report.md`.

## Adding a new case

Add an entry to `EVAL_CASES` in `eval/cases.py` - a `query` string plus
an `expect` dict of whichever checks apply (all optional; see the
existing cases for the available keys). The best new cases come from a
real bug you just found by hand, the same way every case already in
there did - see each case's own comment for which fix it's guarding.

## Where this could go next

- An LLM-as-judge pass (a second model scores each itinerary 1-5 on
  "does this feel like a real, specific trip to this place") would
  catch quality issues no heuristic here can - at the cost of an extra
  LLM call per case, plus the judge's own accuracy to trust
- LangSmith tracing (see `LANGSMITH_SETUP.md`) is a different, related
  tool - it shows you what happened inside ONE run (per-node timing,
  the LLM prompts/responses); this harness checks the OUTPUT of many
  runs against expectations. Genuinely complementary, not overlapping.
