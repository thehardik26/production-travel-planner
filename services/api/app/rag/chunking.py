"""
Chunking for the destination-guide knowledge base.

Only the strategy actually used in production is kept here (the
prototype this was ported from had four - recursive/semantic/parent-
child/metadata-aware - but destination guides are short, hand-curated
prose, not scraped Wikipedia dumps or attraction databases, so the
extra strategies were speculative generality with no caller. Semantic
(paragraph-aware) chunking is the one that matters: it keeps a guide's
"budget tips" paragraph from being split mid-thought against its
"best time to visit" paragraph, which a fixed-size character splitter
would happily do.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class Chunk:
    """A single indexable piece of text plus its metadata. Deliberately
    NOT a langchain Document - this project doesn't otherwise depend on
    langchain, and a plain dataclass-ish object is one less dependency
    for something this small."""

    __slots__ = ("content", "metadata")

    def __init__(self, content: str, metadata: dict[str, Any]):
        self.content = content
        self.metadata = metadata


def semantic_chunk(
    text: str,
    metadata: dict[str, Any] | None = None,
    max_chunk_size: int = settings.RAG_CHUNK_SIZE,
) -> list[Chunk]:
    """Split at paragraph boundaries, packing consecutive paragraphs
    together up to max_chunk_size rather than splitting mid-paragraph."""
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[Chunk] = []
    current = ""

    def _flush():
        if current:
            chunks.append(Chunk(current, {**(metadata or {}), "chunk_index": len(chunks)}))

    for para in paragraphs:
        if current and len(current) + len(para) + 2 > max_chunk_size:
            _flush()
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    _flush()

    for c in chunks:
        c.metadata["total_chunks"] = len(chunks)

    logger.debug("semantic_chunk: %d paragraphs -> %d chunks", len(paragraphs), len(chunks))
    return chunks
