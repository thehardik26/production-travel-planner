# Production MCP Multi-Agent Travel Planner — Architecture Blueprint

This is the plan we'll implement step by step, in `production-travel-planner/`,
alongside your existing demo projects (`mcp-travel-planner/` = mock data,
`mcptoolcalling/` = real free APIs). Nothing has been built yet — this
document is the blueprint we agree on before writing code, so we don't have
to redo work later.

## 1. Request lifecycle (what happens for one API call)

1. Client sends `POST /api/trips/plan` → hits an API Gateway / load balancer (TLS termination, rate limiting).
2. FastAPI receives it. Pydantic validates the request shape. Auth middleware verifies the OAuth2/JWT token and attaches the authenticated user to the request context — **enforced via `Depends()` on the route**, not optional.
3. The validated, authenticated request is handed to the LangGraph orchestrator, which opens (or resumes) a durable thread backed by a **Postgres checkpointer** — so if the process crashes mid-workflow, it resumes from the last completed step instead of restarting.
4. `IntentAgent` parses the request. If relevant, it queries the RAG pipeline for user preference history or destination context.
5. `ResearchAgent` fans out parallel calls through MCP clients to the MCP tool servers (flights, hotels, weather, attractions, transport). Each MCP client checks **Redis** first; on a cache miss it calls the real MCP server, which calls the external API, and the response is cached with an appropriate TTL.
6. The RAG pipeline (when invoked) does hybrid retrieval: dense vector search in **Qdrant** + sparse keyword search (**BM25**) run in parallel, results are merged (reciprocal rank fusion), then a **cross-encoder reranker** reorders the top candidates before they're injected into an agent's prompt.
7. `BudgetAgent`, `SchedulingAgent`, `VerificationAgent` run in sequence. LangGraph checkpoints state to Postgres after every node.
8. Every LLM call and MCP tool call is traced to **LangSmith** (prompt, tokens, latency, cost) and emits metrics/logs to Prometheus + a log aggregator.
9. The final itinerary is persisted to Postgres (`trips` table) and returned to the client.

## 2. Repo / folder structure (industry-standard monorepo, services split by deployability)

```
production-travel-planner/
├── services/
│   ├── api/                          # the FastAPI app — orchestration lives here
│   │   ├── app/
│   │   │   ├── api/                  # routes, request/response schemas
│   │   │   ├── auth/                 # OAuth2/JWT verification, RBAC, Depends() guards
│   │   │   ├── orchestration/        # LangGraph graph definition + Postgres checkpointer config
│   │   │   ├── agents/               # intent, research, budget, scheduling, verification
│   │   │   ├── mcp_clients/          # one client wrapper per MCP server, with Redis caching built in
│   │   │   ├── rag/                  # hybrid retrieval: qdrant_client.py, bm25_index.py, fusion.py, reranker.py
│   │   │   ├── core/                 # settings, structured logging, OpenTelemetry/LangSmith setup
│   │   │   ├── db/                   # SQLAlchemy models + Alembic migrations
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── mcp-flights-server/           # standalone deployable MCP server (own container)
│   ├── mcp-hotels-server/
│   ├── mcp-weather-server/
│   ├── mcp-attractions-server/
│   └── mcp-transport-server/
│
├── infra/
│   ├── docker-compose.yml            # local dev: postgres, redis, qdrant, all services wired together
│   ├── k8s/                          # Kubernetes manifests / Helm chart for each service
│   └── .env.example
│
├── shared/
│   └── schemas/                      # Pydantic contracts shared between api and mcp servers
│
└── .github/workflows/                # CI: lint, test, build+push images, deploy
```

**Why split MCP servers into their own `services/` folders instead of one `mcp_server/` file:** in production each MCP server is its own deployable unit — reachable over HTTP/SSE (not the demo's stdio-subprocess model), independently scaled, independently rate-limited, and independently versioned. The flights server getting slow shouldn't block weather.

## 3. Tech stack per concern

| Concern | Tool | Role |
|---|---|---|
| API framework | FastAPI | request validation, routing |
| Auth | OAuth2 / JWT (`python-jose`), enforced via `Depends()` | authn + authz on every protected route |
| Orchestration | LangGraph + Postgres checkpointer | durable multi-agent state machine |
| Tool calling | MCP (HTTP/SSE transport) | standardized agent↔tool interface |
| Cache | Redis | tool-response cache, session state, idempotency keys |
| System of record | PostgreSQL | users, trips, bookings, checkpoints, audit log |
| Vector search | Qdrant | dense embeddings for destination/guide content |
| Keyword search | BM25 (`rank-bm25` or Elasticsearch) | sparse retrieval, exact-term matches |
| Reranking | Cross-encoder (Cohere Rerank or local `bge-reranker`) | reorder hybrid results by relevance |
| Tracing | LangSmith | per-call LLM/agent/tool tracing, evals |
| Metrics/logs | Prometheus + Grafana, structured JSON logs | operational monitoring, alerting |
| Containerization | Docker | one image per service |
| Deployment | Kubernetes (Helm) | scaling, health checks, rollout |
| CI/CD | GitHub Actions | lint/test/build/deploy pipeline |

## 4. Phased build order

We'll implement in this order — each phase produces something runnable before moving to the next, so nothing is "half-done" for long.

1. **Foundation** — repo/folder scaffolding, `docker-compose.yml` (Postgres + Redis + Qdrant running locally), config/env management.
2. **Data layer** — Postgres schema + Alembic migrations, SQLAlchemy models, Redis client wrapper.
3. **Auth** — OAuth2/JWT actually enforced on routes via `Depends()`, RBAC.
4. **MCP tool layer** — convert the stdio demo servers into persistent HTTP/SSE services, add Redis caching inside each MCP client.
5. **Orchestration** — LangGraph wired to the Postgres checkpointer for durable execution.
6. **RAG** — Qdrant collection + embeddings pipeline, BM25 index, hybrid fusion, reranker.
7. **Observability** — LangSmith tracing, structured logging, Prometheus metrics.
8. **Containerization & deployment** — Dockerfile per service, Kubernetes manifests, CI/CD pipeline.
9. **Testing & hardening** — load testing, security review.

## Status

Nothing implemented yet — this is the agreed blueprint. Next: confirm this
matches what you want, then we start Phase 1 (Foundation).
