"""
Typed entry point ResearchAgent calls - same shape as the
app/mcp_clients/*.py wrappers (a plain async function, no caller-visible
knowledge of retrieval/embeddings/reranking underneath), even though
this isn't an MCP tool call. Keeping the same "callers depend on a
name and a shape, not on how it's fetched" contract means
ResearchAgent's `_safe(name, coro)` wrapping pattern (see
app/agents/research_agent.py) works identically for this as for the
five real MCP tools - one more concurrent, independently-failing
lookup, no special-casing needed.

NOTE (22 Aug 2026): @traceable added for the same reason as the 5
mcp_clients/*.py wrappers (see weather_client.py's NOTE) - this is
ResearchAgent's 6th concurrent lookup, so leaving it undecorated would
have made LangSmith's "research" span breakdown look complete while
actually missing one branch (RAG retrieval, which has its own embed +
search + rerank cost worth seeing separately from the 5 MCP calls).
"""
from __future__ import annotations

from langsmith import traceable

from app.rag.retrieval import retriever


@traceable(name="destination_guide", run_type="retriever")
async def get_destination_guide(destination: str, preferences: list[str] | None = None) -> dict | None:
    """Retrieve destination-guide context for `destination`, optionally
    steered by the traveler's stated preferences (e.g. ["food",
    "beaches"] biases the query toward guide passages about those
    topics rather than generic overview text).

    Returns None (not an empty dict) when nothing relevant was found -
    e.g. a destination with no seed-corpus coverage yet - so callers
    can distinguish "we looked and there's nothing" from "we haven't
    looked", the same None-vs-empty-list convention already used for
    `weather` (dict | None) vs `attractions`/`hotels` (list, possibly
    empty) in orchestration/state.py.
    """
    if not destination:
        return None

    query = destination
    if preferences:
        query = f"{destination} - {', '.join(preferences)}"

    result = await retriever.retrieve(query, metadata_filter=None)
    documents = result["documents"]
    if not documents:
        return None

    return {
        "query": query,
        "passages": [
            {
                "content": d["content"],
                "title": d["metadata"].get("title"),
                "score": round(d.get("score", 0.0), 3),
            }
            for d in documents
        ],
        "avg_confidence": result["avg_confidence"],
    }
