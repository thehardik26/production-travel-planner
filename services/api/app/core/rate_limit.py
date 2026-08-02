"""
Rate limiting, backed by Redis instead of in-process memory.

Why this matters for multi-user: if the limiter counted requests in a
plain Python dict, each running API process would have its own counter.
Run 3 replicas of this service behind a load balancer (completely normal
for handling more concurrent users) and a client could get 3x the
intended limit just by getting load-balanced across processes, because
each process only sees its own third of that client's requests. Backing
the counter with Redis makes it one shared counter every replica reads
and writes, so the limit is correct regardless of how many API
processes are running.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
)
