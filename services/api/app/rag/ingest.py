"""
One-time (per-process, idempotent-per-collection) seeding of the RAG
knowledge base into Qdrant + the in-memory BM25 corpus.

Called from app/main.py's lifespan, best-effort - see `ensure_ready()`.
Deliberately NOT a route or a request-path dependency: ingestion is a
few seconds of embedding-model work over a small, static corpus, not
something any user request should ever wait on or be able to trigger.
"""
from __future__ import annotations

import logging

from app.core.config import settings
from app.rag.chunking import semantic_chunk
from app.rag.knowledge_base import SEED_KNOWLEDGE
from app.rag.retrieval import HybridRetriever

logger = logging.getLogger(__name__)


async def _ensure_collection(retriever: HybridRetriever) -> None:
    from qdrant_client.models import Distance, VectorParams

    client = await retriever._get_qdrant()
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]

    if settings.QDRANT_COLLECTION not in names:
        await client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=settings.RAG_EMBEDDING_DIMENSIONS, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection: %s", settings.QDRANT_COLLECTION)


async def ingest_seed_knowledge(retriever: HybridRetriever) -> int:
    total = 0
    for item in SEED_KNOWLEDGE:
        chunks = semantic_chunk(
            item["content"],
            metadata={**item["metadata"], "title": item["title"]},
        )
        await retriever.add_documents(chunks)
        total += len(chunks)
    return total


async def ensure_ready(retriever: HybridRetriever) -> None:
    """Best-effort startup hook: create the Qdrant collection and seed
    it if empty, THEN (regardless of whether that worked) make sure the
    in-memory BM25 corpus is populated.

    NOTE (21 Aug 2026): the Qdrant setup and the BM25 seeding used to be
    one all-or-nothing sequence - if `_ensure_collection` raised (Qdrant
    unreachable), the function exited before ever reaching the BM25
    corpus population, so a Qdrant outage silently took BM25 down with
    it even though BM25 has no dependency on Qdrant at all. Found via a
    real run where Qdrant genuinely wasn't running: `retrieve()` still
    "succeeded" (no exception) but both its dense AND sparse legs came
    back empty, for two unrelated reasons, because of this. Same
    partial-failure-isolation principle as ResearchAgent's `_safe()`
    wrapping five independent tools - Qdrant being down should cost RAG
    its dense leg, not both legs.

    The Qdrant setup is now its own try/except; BM25 seeding always
    runs after it, Qdrant-up or not. `ingest_seed_knowledge` already
    calls `HybridRetriever.add_documents`, which independently
    try/excepts its own Qdrant upsert per chunk (see retrieval.py) -
    calling it with Qdrant down just means every chunk's dense-index
    attempt fails individually and BM25 still gets populated, so this
    isn't a wasted call even in the worst case.
    """
    qdrant_ready = False
    try:
        await _ensure_collection(retriever)
        existing = await retriever.collection_point_count()
        qdrant_ready = True
    except Exception as exc:
        logger.warning("RAG: Qdrant unavailable at startup (%s) - continuing with BM25-only", exc)
        existing = 0

    if qdrant_ready and existing > 0:
        logger.info("RAG: Qdrant collection already has %d points, re-seeding BM25 only", existing)
        # Dense index already seeded from a prior run - only rebuild the
        # in-memory BM25 corpus, don't re-embed/re-upsert into Qdrant.
        # BM25Okapi has no persistence layer here, so this in-memory
        # corpus is rebuilt from SEED_KNOWLEDGE on every restart
        # regardless - cheap, and keeps the two indexes from drifting.
        for item in SEED_KNOWLEDGE:
            chunks = semantic_chunk(item["content"], metadata={**item["metadata"], "title": item["title"]})
            retriever._corpus.extend(c.content for c in chunks)
            retriever._corpus_meta.extend(c.metadata for c in chunks)
        retriever._bm25_index = None
        return

    count = await ingest_seed_knowledge(retriever)
    logger.info("RAG: seeded knowledge base, %d chunks indexed (qdrant_ready=%s)", count, qdrant_ready)
