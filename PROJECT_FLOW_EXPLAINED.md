# Production Travel Planner — Full Project Flow

A teaching-oriented walkthrough of `production-travel-planner`: what it is, how a request actually moves through the system, and the specific engineering decisions worth being able to explain — especially around handling multiple concurrent users, which is the recurring theme of this build.

## 1. What this project is

A trip-planning backend where a user types one free-text sentence ("5 day trip to Goa from Mumbai, budget 60000 INR, 2 travelers, love food and beaches") and gets back a full itinerary — built from real weather, flight, hotel, attraction, and transport data, assembled by a multi-agent AI pipeline.

It is deliberately over-engineered relative to a toy project, on purpose: every phase adds one production concern (auth, caching, rate limiting, retries, guardrails, multi-user isolation) that a real system needs and a tutorial-grade project usually skips.

## 2. The three layers, top to bottom

**Frontend** — a React (Vite) single-page app. Handles signup/login, a trip-request form, trip history, and renders the itinerary/budget/warnings.

**Backend API (FastAPI)** — the only service the frontend talks to. Owns authentication, persistence (Postgres), and orchestrates trip planning by running a LangGraph multi-agent pipeline.

**MCP tool servers (×5)** — `mcp-weather-server`, `mcp-flights-server`, `mcp-hotels-server`, `mcp-attractions-server`, `mcp-transport-server`. Each is its own standalone process exposing exactly one tool over HTTP (the Model Context Protocol's Streamable HTTP transport). The API calls these over the network — it has zero knowledge of what's inside them.

Three pieces of shared infrastructure sit underneath: **Postgres** (users, trips, and LangGraph's own checkpoint tables), **Redis** (tool-response cache + rate limiting), and **Qdrant** (provisioned for Phase 6 / RAG, not used yet).

## 3. Why MCP tool servers are separate processes, not functions

This is the single most important architectural decision to explain. Every "tool" (get_weather, search_flights, etc.) could have been a plain Python function imported into the API. Instead, each one is:

- Its own OS process, with its own port, its own `requirements.txt`, its own Dockerfile.
- Talked to over HTTP (MCP's Streamable HTTP transport), not called in-process.
- Independently deployable, scalable, and restartable.

**Why this matters for multiple users:** if `search_attractions` starts timing out under load (the free OpenStreetMap Overpass API is exactly this kind of flaky), only that one server is affected. The API, and every other tool, keeps working. If this were all one monolith, a slow function call blocks the whole request-handling process. This is the same reasoning behind microservices in general, demonstrated at a scale small enough to actually read end to end.

## 4. The request lifecycle — a concrete walkthrough

Follow one call to `POST /api/trips/plan` from start to finish.

1. **Auth.** The request carries `Authorization: Bearer <JWT>`. `get_current_user` (a FastAPI dependency) decodes it and loads the user from Postgres. No session state is kept anywhere — the token itself is the proof of identity. This is what makes the API horizontally scalable: any replica can handle any request, because nothing about "who's logged in" lives in that replica's memory.

2. **Graph invocation.** The route grabs the ONE LangGraph instance created at app startup (`app.state.graph`) and calls `.ainvoke(initial_state, config={"configurable": {"thread_id": trip_id}})`. A fresh `trip_id` (UUID) is generated per request and used as the `thread_id` — this is what gives each request its own isolated slice of state in LangGraph's Postgres-backed checkpointer, so two users' concurrent requests can never see or corrupt each other's data.

3. **Intent agent.** Calls Groq (an LLM) to turn the free-text query into structured fields: destination, dates, budget, travelers, preferences. The system prompt is given the real current date explicitly (`{today}`) so the model can't hallucinate a date in the past. If the LLM call fails for any reason, a regex-based heuristic fallback kicks in instead of crashing the whole request.

4. **Budget gate agent.** A pure rule-based check — no LLM, no network call. Computes a conservative minimum plausible cost (₹1500/day/traveler floor) and compares it to the stated budget. If the budget is far below that floor, the graph short-circuits straight to the end via a LangGraph *conditional edge* — no tool calls, no second LLM call. This exists purely to fail fast: don't spend network calls and LLM tokens on a request that can never succeed.

5. **Research agent** (only runs if the budget passed the gate). Fires all 5 MCP tool calls **concurrently** with `asyncio.gather`, each wrapped so one tool's failure doesn't cancel the others. Each call goes through a shared cache-aside layer: check Redis first (keyed by tool name + arguments, not by user — two users asking about the same city on the same date share one cache entry), call the MCP server on a miss, store the result with a TTL.

6. **Budget agent.** Rule-based again: sums whatever real prices came back (flights, hotels), flags missing estimates, computes over/under budget.

7. **Scheduling agent.** A second Groq call — takes all the real data gathered so far and writes a day-by-day itinerary. If this LLM call fails, a round-robin fallback itinerary is built instead.

8. **Verification agent.** Rule-based sanity checks on the final output (right number of days, no empty days, budget within range) — surfaces problems into a `warnings` list rather than blocking the response.

9. **Persistence + response.** The full result is saved to the `trips` table (scoped to `user_id`), and a trimmed response goes back to the frontend.

## 5. Multi-user handling — the interview answer, itemized

Every one of these is a deliberate, explainable decision, not a default:

- **Stateless auth (JWT):** any API replica can serve any request; no sticky sessions needed.
- **Explicit DB connection pooling** (`pool_size`, `max_overflow`, `pool_pre_ping=True`): bounds how many concurrent Postgres connections one API process opens, instead of one-connection-per-request exhausting the database under load.
- **Redis-backed rate limiting** (`slowapi` + `storage_uri=REDIS_URL`), not in-memory: an in-memory counter would give each horizontally-scaled replica its own independent (and thus wrong) limit.
- **Cache keyed by request content, not by user** (`hash(tool_name + args)`): the point of caching is that concurrent users asking the same question share the benefit.
- **LangGraph `thread_id` per request:** state isolation between concurrent trip-planning runs, backed by Postgres so it survives process restarts.
- **`asyncio.gather` with per-tool error isolation:** one flaky external API degrades one field of the response, not the whole request.
- **Retry with exponential backoff + jitter**, scoped only to transient failures (429/403/504/network errors), never to business-logic errors (bad city name) — retrying those wastes quota on a guaranteed-identical failure.
- **The budget gate:** fail cheap and fast before committing to expensive work, the same principle as input validation at any API boundary.

## 6. What's real data and what isn't (be honest about this with students)

| Source | Status |
|---|---|
| Weather (Open-Meteo) | Real, live |
| Attractions (OSM Overpass) | Real, live (names/locations exist; no pricing) |
| Transport (OSM Overpass) | Real, live (no fare data) |
| Hotels (Google Places) | Real names/locations; **no pricing at all** in this API tier |
| Flights (Duffel) | Real API call, but running in **test mode** — returns a simulated airline with fake prices, not real market data |
| Itinerary text | AI-composed from the real data above, not sourced from an authoritative itinerary API |

The frontend now shows a "Test data" badge next to any budget number derived from flight prices, specifically so this limitation isn't silently hidden.

## 7. What's built vs. what's deferred

**Built:** foundation infra (Docker Compose: Postgres/Redis/Qdrant), Postgres schema + Alembic migrations, JWT auth, all 5 MCP tool servers as independent HTTP services with Redis caching and retries, the LangGraph multi-agent pipeline with a budget guardrail, and a React frontend.

**Not built yet:** Phase 6 (RAG — Qdrant hybrid dense/sparse retrieval, deferred until everything above is verified end to end), Phase 7 (LangSmith observability), Phase 8 (full CI/CD), Phase 9 (broader test hardening).

## 8. One good in-class exercise

Have students trace what happens if `mcp-attractions-server` is simply killed mid-demo: the API stays up, `/api/trips/plan` still returns a 200 with a real itinerary, and the response's `warnings` array names exactly which tool failed and why. That single behavior touches almost everything in section 5 at once — it's the fastest way to make "graceful degradation" concrete instead of abstract.
