"""
The real trip-planning endpoint (`POST /api/trips/plan`) - everything
built since Phase 1 exists to make this route possible: auth identifies
who's asking, the MCP tool layer fetches real data, and this route runs
that data through the LangGraph agent pipeline (Phase 5) and persists
the result to the `trips` table Phase 2 created.

`request.app.state.graph` is the ONE compiled graph + Postgres
checkpointer opened once at app startup (see app/main.py's lifespan) -
every request reuses it rather than opening a new DB connection pool
per request, which is the same pooling principle as
app/db/database.py's SQLAlchemy engine.

NOTE: deliberately no `from __future__ import annotations` here.
Combined with the @limiter.limit(...) decorator (Phase 4), postponed
(stringified) annotations broke FastAPI's ability to recognize
`payload: TripPlanRequest` as a request body - it silently fell back to
treating it as a query parameter instead (422 "field required" on a
perfectly good POST body). Same underlying category of bug as the
FastMCP note in services/mcp-*-server/server.py: a decorator plus
postponed annotations plus runtime type introspection is a combination
worth avoiding, not just a FastMCP-specific quirk.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.database import get_db
from app.db.models import Trip, User

router = APIRouter(prefix="/api/trips", tags=["trips"])


class TripPlanRequest(BaseModel):
    query: str = Field(
        min_length=3,
        max_length=2000,
        description="Free-text trip request, e.g. '5 day trip to Goa from Delhi starting 2026-08-10, budget 50000 INR, 2 travelers, love food and beaches'",
    )


class TripPlanResponse(BaseModel):
    trip_id: str
    destination: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    budget_summary: dict | None = None
    itinerary: dict | None = None
    warnings: list[str] = []
    errors: list[str] = []


class TripSummary(BaseModel):
    id: str
    query: str
    destination: str | None = None
    created_at: str


@router.post("/plan", response_model=TripPlanResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def plan_trip(
    request: Request,
    payload: TripPlanRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TripPlanResponse:
    graph = request.app.state.graph
    trip_id = str(uuid.uuid4())
    # thread_id scopes this run's checkpointed state - one trip = one
    # thread, so concurrent planning requests (same user or different
    # users) never share or clobber each other's in-progress state.
    config = {"configurable": {"thread_id": trip_id}}

    initial_state = {
        "user_query": payload.query,
        "user_id": current_user.id,
        "errors": [],
        "warnings": [],
    }

    try:
        result = await graph.ainvoke(initial_state, config=config)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"trip planning failed: {exc}") from exc

    stored_itinerary = {
        "intent": {
            "origin": result.get("origin"),
            "destination": result.get("destination"),
            "start_date": result.get("start_date"),
            "end_date": result.get("end_date"),
            "travelers": result.get("travelers"),
            "budget": result.get("budget"),
            "budget_currency": result.get("budget_currency"),
            "preferences": result.get("preferences"),
        },
        "research": {
            "weather": result.get("weather"),
            "flights": result.get("flights"),
            "hotels": result.get("hotels"),
            "attractions": result.get("attractions"),
            "transport": result.get("transport"),
        },
        "budget_summary": result.get("budget_summary"),
        "itinerary": result.get("itinerary"),
        "warnings": result.get("warnings", []),
        "errors": result.get("errors", []),
    }

    trip = Trip(id=trip_id, user_id=current_user.id, query=payload.query, itinerary=stored_itinerary)
    db.add(trip)
    await db.commit()

    return TripPlanResponse(
        trip_id=trip_id,
        destination=result.get("destination"),
        start_date=result.get("start_date"),
        end_date=result.get("end_date"),
        budget_summary=result.get("budget_summary"),
        itinerary=result.get("itinerary"),
        warnings=result.get("warnings", []),
        errors=result.get("errors", []),
    )


@router.get("", response_model=list[TripSummary])
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def list_trips(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TripSummary]:
    # scoped to the authenticated user only - one user can never list
    # (or, in the route below, fetch) another user's trips.
    result = await db.execute(
        select(Trip).where(Trip.user_id == current_user.id).order_by(Trip.created_at.desc())
    )
    trips = result.scalars().all()
    return [
        TripSummary(
            id=t.id,
            query=t.query,
            destination=((t.itinerary or {}).get("intent") or {}).get("destination"),
            created_at=t.created_at.isoformat(),
        )
        for t in trips
    ]


@router.get("/{trip_id}")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def get_trip(
    request: Request,
    trip_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.user_id == current_user.id)
    )
    trip = result.scalar_one_or_none()
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return {
        "id": trip.id,
        "query": trip.query,
        "created_at": trip.created_at.isoformat(),
        **(trip.itinerary or {}),
    }
