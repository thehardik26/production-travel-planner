"""
Cross-encoder reranking - BAAI/bge-reranker-base.

A bi-encoder (embeddings.py) scores query and passage independently,
then compares vectors; a cross-encoder scores the (query, passage) PAIR
jointly, which is slower (can't be precomputed/indexed) but notably
more accurate - exactly why hybrid retrieval fetches a wider candidate
set first (dense + BM25) and only cross-encodes that shortlist, not the
whole corpus.

Same resilience shape as every LLM-ish call elsewhere in this codebase:
if the model can't be loaded (offline environment, no disk space, first
call still downloading), fall back to sorting by the upstream score
instead of failing the request - a slightly-worse-ranked destination
guide snippet beats no snippet.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    MODEL_NAME = "BAAI/bge-reranker-base"
    # See embeddings.py's identical constant (and its 21 Aug 2026 notes)
    # for why this exists and why it's 180s, not the original 20s: bound
    # a first-time model download so a blocked/offline environment fails
    # fast, WITHOUT the bound itself being short enough to misfire on a
    # real but slow connection and permanently disable reranking for the
    # rest of the process.
    LOAD_TIMEOUT_SECONDS = 180

    def __init__(self) -> None:
        self._model: Any = None
        self._available = False
        self._load_attempted = False
        self._load_lock = asyncio.Lock()

    async def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 4,
    ) -> list[dict[str, Any]]:
        if not documents:
            return documents

        try:
            model = await self._get_model()
            if model is None:
                return self._fallback_rank(documents, top_k)

            pairs = [(query, doc["content"]) for doc in documents]
            loop = asyncio.get_event_loop()
            scores = await loop.run_in_executor(None, lambda: model.predict(pairs))

            scored = [
                {**doc, "score": float(score)} for doc, score in zip(documents, scores)
            ]
            scored.sort(key=lambda d: d["score"], reverse=True)
            return scored[:top_k]
        except Exception as exc:
            logger.warning("Reranker failed (%s), falling back to score sort", exc)
            return self._fallback_rank(documents, top_k)

    async def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        if self._load_attempted:
            # Already tried once this process and it didn't work - don't
            # retry the (slow, possibly-blocked) download on every single
            # request; see embeddings.py's identical reasoning.
            return None
        async with self._load_lock:
            if self._model is None and not self._load_attempted:
                self._load_attempted = True
                try:
                    from sentence_transformers import CrossEncoder

                    loop = asyncio.get_event_loop()
                    self._model = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: CrossEncoder(self.MODEL_NAME)),
                        timeout=self.LOAD_TIMEOUT_SECONDS,
                    )
                    self._available = True
                    logger.info("Loaded cross-encoder reranker: %s", self.MODEL_NAME)
                except Exception as exc:
                    logger.warning("Could not load cross-encoder (%s), using score fallback", exc)
                    self._available = False
        return self._model if self._available else None

    @staticmethod
    def _fallback_rank(documents: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        return sorted(documents, key=lambda d: d.get("score", 0.0), reverse=True)[:top_k]
