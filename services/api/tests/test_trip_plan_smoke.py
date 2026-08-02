"""
Smoke test for the full trip-planning flow: signup -> login -> POST
/api/trips/plan -> GET /api/trips -> GET /api/trips/{id}.

This is deliberately a HAPPY-PATH-SHAPED test, not a "zero warnings"
test: individual research tools (hotels, attractions, weather...) can
legitimately come back empty or with a warning for a given city/date
(e.g. a small town with no Google-tagged hotels, a date outside
Open-Meteo's forecast window) without that being a regression. What
this test actually guards against is the class of failure this session
spent hours chasing down one at a time: a wrong MCP server URL, a
server that crashed and won't respond at all, an auth wire-up that
silently breaks, a response shape that no longer matches
TripPlanResponse. Run this after ANY change to agents/, mcp_clients/,
orchestration/, or auth/ - before finding out about a break from a
Swagger click-through.
"""
from __future__ import annotations

from httpx import AsyncClient


async def test_health_check(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_unauthenticated_plan_request_is_rejected(client: AsyncClient):
    # Auth wiring regressions (e.g. a Depends() dropped by accident) are
    # exactly the kind of silent break worth locking in explicitly.
    resp = await client.post("/api/trips/plan", json={"query": "3 day trip to Goa"})
    assert resp.status_code in (401, 403)


async def test_full_trip_plan_flow(client: AsyncClient, auth_headers: dict[str, str]):
    query = (
        "3 day trip to Lonavala from Mumbai starting 2026-08-05, "
        "budget 15000 INR, 2 travelers, love nature and food"
    )

    plan_resp = await client.post(
        "/api/trips/plan",
        json={"query": query},
        headers=auth_headers,
        timeout=60,  # ResearchAgent fans out 5 real network calls - give it room
    )
    assert plan_resp.status_code == 200, f"trip planning failed: {plan_resp.text}"

    body = plan_resp.json()
    assert body["trip_id"]
    # IntentAgent should have pulled a destination out of the free-text
    # query - if this is None, intent parsing (or its Groq fallback) broke.
    assert body["destination"], f"no destination parsed, full response: {body}"
    # SchedulingAgent should always produce SOME itinerary shape, even if
    # individual research tools came back empty - a None itinerary means
    # a node crashed before scheduling ran.
    assert body["itinerary"] is not None, f"no itinerary produced, full response: {body}"
    assert isinstance(body["warnings"], list)
    assert isinstance(body["errors"], list)

    trip_id = body["trip_id"]

    # The trip must actually be persisted and retrievable - proves the DB
    # write in trips.py's plan_trip() succeeded, not just the in-memory
    # response.
    list_resp = await client.get("/api/trips", headers=auth_headers)
    assert list_resp.status_code == 200
    assert any(t["id"] == trip_id for t in list_resp.json())

    get_resp = await client.get(f"/api/trips/{trip_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == trip_id


async def test_get_nonexistent_trip_is_404(client: AsyncClient, auth_headers: dict[str, str]):
    resp = await client.get("/api/trips/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.status_code == 404
