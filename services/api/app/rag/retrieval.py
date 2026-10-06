"""
Hybrid retrieval for the destination-guide knowledge base (Phase 6).

Combines dense vector search (Qdrant) with sparse keyword search
(BM25), merges the two ranked lists with Reciprocal Rank Fusion, then
reranks the fused shortlist with a cross-encoder. Same rationale as
combining Redis cache + real MCP call elsewhere in this codebase:
dense and sparse retrieval fail in different, complementary ways -
dense search finds "warm coastal town" when the guide says "tropical
beaches" but never says the query's exact words; BM25 finds an exact
place name ("Anjuna") that an embedding model might blur into "beach
town in general". Fusing both is more robust than either alone.

MULTI-USER NOTE: this is READ-mostly at request time - every trip-plan
request queries the same small, mostly-static knowledge base. There's
no per-user data here and nothing to isolate between concurrent
requests, unlike LangGraph's per-thread_id state. The one shared,
mutable thing is the BM25 index, which is rebuilt lazily after
ingestion adds documents - see `_bm25_index = None` in add_documents.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings
from app.rag.embeddings import embedding_service
from app.rag.reranking import CrossEncoderReranker

logger = logging.getLogger(__name__)


class HybridRetriever:
    def __init__(
        self,
        collection: str = settings.QDRANT_COLLECTION,
        top_k: int = settings.RAG_TOP_K_RETRIEVAL,
        rerank_top_k: int = settings.RAG_TOP_K_RERANK,
        dense_weight: float = settings.RAG_DENSE_WEIGHT,
        bm25_weight: float = settings.RAG_BM25_WEIGHT,
    ) -> None:
        self.collection = collection
        self.top_k = top_k
        self.rerank_top_k = rerank_top_k
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight
        self._qdrant_client: Any = None
        self._bm25_index: Any = None
        self._corpus: list[str] = []
        self._corpus_meta: list[dict[str, Any]] = []
        self._reranker = CrossEncoderReranker()
        self._ready = False

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Full pipeline. Returns {"documents": [...], "avg_confidence": float}.
        Every stage is independently try/excepted - a Qdrant outage
        degrades to BM25-only, a BM25/reranker failure degrades to
        whatever the other stage found, and total failure degrades to
        an empty result rather than raising (callers - see
        app/rag/destination_guide.py - treat "no guide content" as a
        normal, expected outcome, same as any other ResearchAgent tool
        that comes back empty)."""
        k = top_k or self.top_k

        try:
            dense_results = await self._dense_search(query, k * 2, metadata_filter)
        except Exception as exc:
            logger.warning("RAG dense search failed: %s", exc)
            dense_results = []

        try:
            bm25_results = self._bm25_search(query, k * 2)
        except Exception as exc:
            logger.warning("RAG BM25 search failed: %s", exc)
            bm25_results = []

        fused = self._reciprocal_rank_fusion(
            [dense_results, bm25_results],
            weights=[self.dense_weight, self.bm25_weight],
        )[:k]

        reranked = await self._reranker.rerank(query, fused, top_k=self.rerank_top_k) if fused else fused

        avg_confidence = (
            sum(d.get("score", 0.0) for d in reranked) / len(reranked) if reranked else 0.0
        )

        logger.info(
            "RAG retrieve: query=%r dense=%d bm25=%d fused=%d reranked=%d",
            query[:60], len(dense_results), len(bm25_results), len(fused), len(reranked),
        )

        return {"documents": reranked, "avg_confidence": round(avg_confidence, 3)}

    async def add_documents(self, chunks: list[Any]) -> None:
        """Index chunks into both Qdrant (dense) and the in-memory BM25
        corpus (sparse). Called once at startup by app/rag/ingest.py -
        see main.py's lifespan - not on the request path."""
        self._corpus.extend(c.content for c in chunks)
        self._corpus_meta.extend(c.metadata for c in chunks)
        self._bm25_index = None  # force rebuild on next search

        try:
            client = await self._get_qdrant()
            texts = [c.content for c in chunks]
            embeddings = await embedding_service.embed_texts(texts)

            from qdrant_client.models import PointStruct
            import uuid

            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=emb,
                    payload={"content": c.content, **c.metadata},
                )
                for c, emb in zip(chunks, embeddings)
            ]
            await client.upsert(collection_name=self.collection, points=points)
        except Exception as exc:
            # Dense indexing failed (e.g. Qdrant not running yet) - BM25
            # still has these documents in memory, so retrieval degrades
            # to keyword-only rather than losing the content entirely.
            logger.error("RAG: Qdrant indexing failed (%s) - BM25 index still updated", exc)

    async def collection_point_count(self) -> int:
        """Used by ingest.py to decide whether seeding already ran -
        Qdrant collections persist across restarts (the Postgres volume
        pattern), re-embedding the same static corpus on every boot
        would be pure waste."""
        try:
            client = await self._get_qdrant()
            info = await client.count(collection_name=self.collection, exact=True)
            return info.count
        except Exception:
            return 0

    # ── private ──────────────────────────────────────────────────────

    async def _dense_search(
        self, query: str, k: int, metadata_filter: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        client = await self._get_qdrant()
        query_vector = await embedding_service.embed_query(query)

        qfilter = None
        if metadata_filter:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            qfilter = Filter(
                must=[FieldCondition(key=k, match=MatchValue(value=v)) for k, v in metadata_filter.items()]
            )

        results = await client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=k,
            query_filter=qfilter,
            with_payload=True,
            score_threshold=0.3,
        )
        return [
            {
                "content": r.payload.get("content", ""),
                "metadata": {k: v for k, v in r.payload.items() if k != "content"},
                "score": r.score,
                "source": "dense",
            }
            for r in results
        ]

    def _bm25_search(self, query: str, k: int) -> list[dict[str, Any]]:
        if not self._corpus:
            return []

        if self._bm25_index is None:
            from rank_bm25 import BM25Okapi

            self._bm25_index = BM25Okapi([doc.lower().split() for doc in self._corpus])

        scores = self._bm25_index.get_scores(query.lower().split())
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

        return [
            {
                "content": self._corpus[i],
                "metadata": self._corpus_meta[i],
                "score": float(scores[i]),
                "source": "bm25",
            }
            for i in top_indices
            if scores[i] > 0
        ]

    @staticmethod
    def _reciprocal_rank_fusion(
        result_lists: list[list[dict[str, Any]]],
        weights: list[float] | None = None,
        k: int = 60,
    ) -> list[dict[str, Any]]:
        """RRF score = sum(weight_i / (k + rank_i)). Rank-based (not raw
        score-based) fusion is what lets dense cosine similarities
        (0..1) and BM25 scores (unbounded) combine sensibly without
        one scale drowning out the other."""
        doc_scores: dict[str, float] = {}
        doc_map: dict[str, dict[str, Any]] = {}

        for list_idx, results in enumerate(result_lists):
            weight = weights[list_idx] if weights else 1.0
            for rank, doc in enumerate(results, start=1):
                key = doc["content"][:100]
                rrf = weight / (k + rank)
                doc_scores[key] = doc_scores.get(key, 0.0) + rrf
                if key not in doc_map:
                    doc_map[key] = {**doc, "score": 0.0}
                doc_map[key]["score"] += rrf

        return [doc_map[key] for key in sorted(doc_scores, key=lambda k: doc_scores[k], reverse=True)]

    async def _get_qdrant(self) -> Any:
        if self._qdrant_client is None:
            from qdrant_client import AsyncQdrantClient

            self._qdrant_client = AsyncQdrantClient(url=settings.QDRANT_URL)
        return self._qdrant_client


# Module-level singleton - the BM25 corpus in particular MUST be shared
# across requests within a process (it's built once at startup, not
# per-request), same reasoning as embedding_service in embeddings.py.
retriever = HybridRetriever()
