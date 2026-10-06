"""
Local embedding service - BAAI/bge-small-en-v1.5 via sentence-transformers.

Phase 6 (RAG). NOTE (21 Aug 2026): the earlier prototype this was ported
from tried OpenAI's embeddings API first and fell back to a local model
only on failure. That's backwards for THIS project - every other LLM-ish
dependency here (Groq for chat, Open-Meteo/OSM for tool data) is
deliberately free-tier/keyless so the whole stack runs without anyone
having to hand over a credit card. Requiring an OPENAI_API_KEY just for
embeddings would be the one place that broke that pattern, for a
capability (semantic search over a small internal corpus) that a small
local model handles perfectly well. So: local-only, no fallback needed
because there's nothing above it to fall back FROM.

Cost of that choice: the first embed call in a fresh process downloads
the model from Hugging Face (~130MB) and loads it into memory - a few
seconds, once, lazily on first use rather than at import time (so
importing this module in a context that never calls it, e.g. a unit
test for something unrelated, stays fast).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Wraps a local sentence-transformers bi-encoder with an in-memory
    cache (same reasoning as mcp_clients: repeated queries for the same
    text - e.g. two users' trip requests both mentioning "Goa beaches" -
    shouldn't re-run the model)."""

    # Bound how long a first-time model download/load is allowed to take
    # before a live request gives up on it. NOTE (21 Aug 2026): originally
    # 20s, found via a run where Hugging Face was unreachable - without a
    # bound, a blocked/offline environment made every request that needed
    # a dense-search embedding hang for tens of seconds retrying the
    # download, one request at a time, instead of failing in ~1s. Same
    # "cheap deliberate failure beats an expensive silent retry loop"
    # principle as the budget gate in budget_gate_agent.py.
    #
    # Raised to 180s (21 Aug 2026, second finding): 20s was too short for
    # the OTHER real case - a genuinely working connection, just not fast
    # enough to pull this model's ~130MB in under 20 seconds. Once
    # _load_failed flips, it stays flipped for the rest of the process
    # (see the comment below) - so a slow-but-succeeding first download
    # was permanently and silently disabling dense search for that whole
    # run, even after the download quietly finished seconds later in the
    # background. 180s comfortably covers a slow first pull; the fast
    # path (model already cached on disk from a previous run) is
    # unaffected either way, since that load takes well under a second.
    LOAD_TIMEOUT_SECONDS = 180

    def __init__(self, model_name: str = settings.RAG_EMBEDDING_MODEL) -> None:
        self.model_name = model_name
        self._cache: dict[str, list[float]] = {}
        self._model: Any = None
        self._load_failed = False
        self._load_lock = asyncio.Lock()

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch, using the cache for anything already seen."""
        results: list[list[float] | None] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for i, text in enumerate(texts):
            key = self._cache_key(text)
            if key in self._cache:
                results[i] = self._cache[key]
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

        if uncached_texts:
            embeddings = await self._encode(uncached_texts)
            for idx, emb in zip(uncached_indices, embeddings):
                self._cache[self._cache_key(texts[idx])] = emb
                results[idx] = emb

        return [r for r in results if r is not None]

    async def embed_query(self, query: str) -> list[float]:
        results = await self.embed_texts([query])
        return results[0]

    async def _encode(self, texts: list[str]) -> list[list[float]]:
        model = await self._get_model()
        loop = asyncio.get_event_loop()
        # sentence-transformers is sync/CPU-bound - run it off the event
        # loop so one embedding batch doesn't stall every other
        # concurrent request the API is handling (same reasoning as the
        # reranker in reranking.py).
        return await loop.run_in_executor(
            None,
            lambda: model.encode(texts, normalize_embeddings=True).tolist(),
        )

    async def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        if self._load_failed:
            # Already tried and timed out/failed once this process - do
            # NOT retry on every request (that's exactly the slow-retry-
            # loop this timeout exists to avoid). A process restart (or a
            # future "retry after N minutes" if this ever matters enough
            # to add) is what re-attempts it, not the next unlucky request.
            raise RuntimeError(f"embedding model '{self.model_name}' unavailable this process (previous load failed)")
        async with self._load_lock:
            if self._model is None and not self._load_failed:
                from sentence_transformers import SentenceTransformer

                loop = asyncio.get_event_loop()
                try:
                    self._model = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: SentenceTransformer(self.model_name)),
                        timeout=self.LOAD_TIMEOUT_SECONDS,
                    )
                    logger.info("Loaded local embedding model: %s", self.model_name)
                except Exception:
                    self._load_failed = True
                    raise
        return self._model

    def _cache_key(self, text: str) -> str:
        return hashlib.md5(f"{self.model_name}:{text}".encode()).hexdigest()

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        arr_a, arr_b = np.array(a), np.array(b)
        norm_a, norm_b = np.linalg.norm(arr_a), np.linalg.norm(arr_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(arr_a, arr_b) / (norm_a * norm_b))


# Module-level singleton - one loaded model shared across every request
# in this process, same pattern as app/core/redis_client.py's shared
# connection rather than one-per-call.
embedding_service = EmbeddingService()
