# Production Travel Planner

A trip-planning backend where a user types one free-text sentence — *"5 day trip to Goa from Mumbai, budget 60000 INR, 2 travelers, love food and beaches"* — and gets back a full itinerary, built from real weather, flight, hotel, attraction, and transport data, assembled by a multi-agent AI pipeline (FastAPI + LangGraph + RAG).

This project is **deliberately over-engineered** relative to a typical class demo, on purpose: every layer adds one real production concern (auth, caching, rate limiting, retries, guardrails, resilience, evaluation) that a tutorial-grade project usually skips. It's meant to be read end to end, not just run.

---

### 📚 Documentation Hub

| Guide | Description |
| :--- | :--- |
| 📖 [**PROJECT_OVERVIEW.md**](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/PROJECT_OVERVIEW.md) | **Start here.** System architecture, components, directory map, and request flows. |
| 🔑 [**ENV_GUIDE.md**](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/ENV_GUIDE.md) | Complete reference for all `.env` files, API keys, defaults, and fallbacks. |
| 🤖 [**AGENTS_AND_WORKFLOW.md**](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/AGENTS_AND_WORKFLOW.md) | Deep dive into the 6 LangGraph agents, shared state schema, and recovery mechanisms. |
| 🚀 [**HOW_TO_RUN.md**](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/HOW_TO_RUN.md) | Step-by-step instructions to run, stop, and troubleshoot the services. |
| ☁️ [**AZURE_DEPLOYMENT_GUIDE.md**](file:///c:/Users/hardi/OneDrive/Desktop/Ai%20Agentic%20Travel%20Planner/production-travel-planner/AZURE_DEPLOYMENT_GUIDE.md) | Production cloud deployment to Azure Kubernetes Service (AKS). |

---


## Problem statement

Most "AI travel planner" demos are a single LLM prompt with no real data behind it. This project asks a harder question: what does it actually take to turn that into something closer to a real, multi-user backend? Specifically:

- **Real data, not invented text** — weather, attractions, transport, and (partially) hotels/flights come from live external APIs, not the LLM's imagination.
- **Multiple specialized agents, not one giant prompt** — parsing, research, budgeting, scheduling, and verification are separate steps, each using an LLM only where language-understanding is actually needed (see [Agents](#agents-what-each-one-actually-does) below).
- **Multi-user safety** — the system is designed so concurrent users never corrupt each other's state, and one flaky external API never takes down the whole app.
- **Honesty about limitations** — every corner cut for cost/time reasons is documented, not hidden (see [What's real and what isn't](#whats-real-data-and-what-isnt)).

## Architecture — three layers

```
Frontend (React/Vite)
   │  signup/login, trip form, history, itinerary + budget + warnings display
   ▼
API (FastAPI)  ──────────────────────────────────────────────
   │  auth, persistence (Postgres), rate limiting (Redis),
   │  orchestrates a LangGraph multi-agent pipeline
   ▼
5 independent MCP tool servers (own process, own port, own Dockerfile each)
   mcp-weather-server · mcp-flights-server · mcp-hotels-server
   mcp-attractions-server · mcp-transport-server
   │
   ▼
External APIs: Open-Meteo, Duffel, Google Places, OpenStreetMap Overpass
```

**Why the 5 tool servers are separate processes, not plain Python functions:** each one could have been a function imported straight into the API. Instead each is its own OS process, reachable only over HTTP (MCP's Streamable HTTP transport). If `mcp-attractions-server` (which depends on the free, occasionally-flaky OSM Overpass API) slows down or dies, only that one tool is affected — the API and every other tool keep working. A monolith would have one slow call block the whole request-handling process. This is the single most important design decision in the project to be able to explain.

Shared infra underneath: **Postgres** (users, trips, LangGraph's own checkpoint state), **Redis** (tool-response cache + rate limiting), **Qdrant** (optional — see [RAG](#rag--destination-guides)).

## Agents — what each one actually does

The graph (`services/api/app/orchestration/graph.py`) runs six nodes, mostly in a straight line with one conditional branch:

| Agent | Type | Why |
|---|---|---|
| `IntentAgent` | LLM (Groq) + heuristic fallback | Parsing open-ended free text into structured fields is exactly what an LLM is good at and regex is bad at. If the LLM call fails, a keyword-matching fallback keeps the request alive instead of crashing. |
| `BudgetGateAgent` | Rule-based, no LLM | Cheap sanity check right after intent parsing: if the stated budget is far below a conservative floor, the graph short-circuits straight to the end via a LangGraph conditional edge — no wasted tool calls or second LLM call on a request that can never succeed. |
| `ResearchAgent` | Orchestrator | Fires all 5 MCP tools **and** the RAG destination-guide lookup concurrently (`asyncio.gather`), each wrapped so one tool's failure doesn't cancel the others. |
| `BudgetAgent` | Rule-based, no LLM | Sums real prices, converts currencies via a free FX API, and computes over/under-budget. Deliberately not an LLM call — arithmetic doesn't need one. |
| `SchedulingAgent` | LLM (Groq) + rule-based fallback | Turns the research results into a day-by-day itinerary, grounded in real attraction/transport data and (when available) RAG destination-guide passages. Falls back to a round-robin scheduler if the LLM call fails. |
| `VerificationAgent` | Rule-based, no LLM | Final sanity checks (right number of days, no empty days, budget sane) — never blocks the response, just surfaces problems into a `warnings` list. |

Not every agent is an LLM call on purpose — using one only where the task genuinely needs language understanding is itself a deliberate design decision, worth being able to explain.

**What this is *not*, honestly:** this is a fixed, human-authored multi-agent *workflow* (LangGraph `StateGraph` with one conditional edge), not a fully autonomous agent. No node dynamically plans its own next step, no ReAct-style reasoning loop lets an LLM choose which tool to call, there's no self-correction/reflection loop, and each request is single-shot (no multi-turn conversation memory across requests, even though the underlying Postgres checkpointer could support it).

## Multi-user handling

The recurring theme of this build. Every one of these is deliberate:

- **Stateless JWT auth** — any API replica can serve any request, no sticky sessions.
- **Explicit DB connection pooling** (bounded `pool_size`/`max_overflow`, `pool_pre_ping=True`) instead of one connection per request.
- **Redis-backed rate limiting**, not in-memory — an in-memory counter would give each horizontally-scaled replica its own independent (wrong) limit.
- **Cache keyed by request content, not by user** — two users asking about the same city/date share one cache entry.
- **A fresh LangGraph `thread_id` per request** — isolates concurrent trip-planning runs from each other, backed by Postgres so state survives a process restart.
- **Retry with exponential backoff + jitter**, scoped only to transient failures (429/503/network errors) — never retried on business-logic errors like a bad city name.

## RAG — destination guides

Hybrid retrieval (dense vector search + BM25 sparse search, merged by reciprocal rank fusion, then reranked by a cross-encoder) over a small hand-written destination-guide corpus. Local embedding/reranking models (`BAAI/bge-small-en-v1.5` + `bge-reranker-base`), not a paid API — matches the project's free-tier-where-possible philosophy. Qdrant (the dense-vector store) is genuinely optional: if it's unreachable at startup, retrieval silently degrades to BM25-only rather than failing the whole request. The seed corpus (`app/rag/knowledge_base.py`) is illustrative starter content for a handful of cities, not verified, comprehensive travel data.

## What's real data and what isn't

Be upfront about this — it matters for anyone demoing or extending the project:

| Source | Status |
|---|---|
| Weather (Open-Meteo) | Real, live |
| Attractions (OSM Overpass) | Real, live names/locations — no pricing |
| Transport (OSM Overpass) | Real, live — no fare data |
| Hotels (Google Places) | Real names/locations — **no pricing at all** in this API tier |
| Flights (Duffel) | Real API call, but in **test mode** — returns a simulated airline with fake prices, not real market data |
| Itinerary text | AI-composed from the real data above, not sourced from an authoritative itinerary API |

The frontend shows a "Test data" badge on any budget figure derived from flight prices, so this limitation isn't silently hidden from the end user.

## What's built vs. what's deferred

Built and working end to end: infra (Docker Compose: Postgres/Redis/Qdrant), Postgres schema + Alembic migrations, JWT auth, all 5 MCP tool servers as independent HTTP services with Redis caching and retries, the LangGraph multi-agent pipeline with a budget guardrail, hybrid RAG retrieval, a React frontend, LangSmith tracing (per-node **and** per-tool spans inside `research`), and a deterministic eval harness (`services/api/eval/`) with its own unit-tested checks.

**Not built yet, honestly:**
- **CI/CD** — `.github/workflows/` is a placeholder README, no actual pipeline.
- **Kubernetes manifests** — same, `infra/k8s/` is a placeholder README.
- **A confirmed live deployment** — `AZURE_DEPLOYMENT_GUIDE.md` is a step-by-step guide to run yourself; nothing in this repo confirms it's ever been executed.
- **Tests for the 5 MCP tool servers** — `services/api` has real test coverage (unit tests + a smoke suite); none of the 5 tool servers have a single test file.
- **Structured logging / metrics (Prometheus, Grafana)** — LangSmith gives per-run tracing, but there's no dashboard/alerting layer.
- **Real booking / affiliate links** — flight and hotel result rows currently link out to a plain Google search, deliberately *not* a real booking flow. Wiring up an actual affiliate/booking integration (e.g. Travelpayouts) is left as the next exercise.

## Running it locally

`start-everything.ps1` / `.bat` (Windows) bring up the full stack: Postgres, Redis, Qdrant, all 5 MCP servers, and the API. See `ARCHITECTURE.md` for the original design blueprint and `PROJECT_FLOW_EXPLAINED.md` for a deeper request-by-request walkthrough. `LANGSMITH_SETUP.md` (in `services/api/`) covers optional tracing setup, and `services/api/eval/README.md` explains the eval harness.

## Repo layout

```
production-travel-planner/
├── frontend/                    React (Vite) SPA
├── services/
│   ├── api/                     FastAPI app - orchestration, auth, RAG, eval
│   │   ├── app/agents/          the 6 LangGraph nodes
│   │   ├── app/mcp_clients/     one cached HTTP client per tool server
│   │   ├── app/rag/             chunking, embeddings, hybrid retrieval
│   │   ├── app/orchestration/   the LangGraph StateGraph definition
│   │   └── eval/                deterministic quality-check harness
│   ├── mcp-weather-server/      each a standalone deployable MCP server
│   ├── mcp-flights-server/
│   ├── mcp-hotels-server/
│   ├── mcp-attractions-server/
│   └── mcp-transport-server/
├── infra/                       docker-compose.yml, k8s/ (placeholder)
└── shared/schemas/               Pydantic contracts shared across services
```
